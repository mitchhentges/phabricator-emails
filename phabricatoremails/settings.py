# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

import configparser
import pathlib
import smtplib
from configparser import ConfigParser
from dataclasses import dataclass
from logging import Logger
from typing import Any

from phabricatoremails import PACKAGE_DIRECTORY
from phabricatoremails.db import DB
from phabricatoremails.logging import create_dev_logger, create_logger
from phabricatoremails.mail import SesMail, SmtpMail, FsMail
from phabricatoremails.worker import RunOnceWorker, PhabricatorWorker
from phabricatoremails.source import FileSource, PhabricatorSource
from sqlalchemy import create_engine


def _parse_logger(config: ConfigParser):
    """Provides a logger set up according to our configuration.

    The regular logger is noisy and implements the MozLog JSON format, so we also
    have a "dev" logger that simply prints out each log without any annotations.
    The correct logger is chosen based on the provided configuration file.
    """
    if config.has_section("dev"):
        return create_dev_logger()
    else:
        return create_logger()


def _parse_pipeline(config: ConfigParser, logger: Logger):
    """Provides data-fetching implementations according to our configuration.

    To facilitate easier local development, we have a few different combinations of
    ways to get data (Phabricator, or just a local file) as well as how we want
    to perform at runtime (fetch-and-send emails once, or on a continuous loop).
    Returns a "data source" and "worker" implementation
    """
    dev_source_file = config.get("dev", "file", fallback=None)
    if dev_source_file:
        # Give RunOnceWorker a garbage feed position, since the position doesn't
        # matter when reading from a file.
        return FileSource(pathlib.Path(dev_source_file).resolve()), RunOnceWorker(0)

    host = config.get("phabricator", "host")
    token = config.get("phabricator", "token")
    story_limit = int(config.get("dev", "story_limit", fallback="100"))
    if host.endswith("/"):
        host = host[:-1]
    source = PhabricatorSource(host, token, story_limit)

    override_since_key = config.get("dev", "since_key", fallback=None)
    if override_since_key:
        return source, RunOnceWorker(int(override_since_key))

    poll_gap_seconds = int(config.get("phabricator", "poll_gap_seconds", fallback="60"))
    return source, PhabricatorWorker(logger, poll_gap_seconds)


def _parse_mail(config: ConfigParser, logger: Logger):
    from_address = config.get("email", "from_address")
    implementation = config.get("email", "implementation")

    if implementation == "ses":
        send_to = config.get("email-ses", "send_to", fallback=None)
        aws_access_key_id = config.get("email-ses", "aws_access_key_id", fallback=None)
        aws_secret_access_key = config.get(
            "email-ses", "aws_secret_access_key", fallback=None
        )
        return SesMail.from_aws_credentials(
            from_address, logger, send_to, aws_access_key_id, aws_secret_access_key
        )

    if implementation == "smtp":
        host = config.get("email-smtp", "host")
        send_to = config.get("email-smtp", "send_to", fallback=None)
        mail_server = smtplib.SMTP(host, timeout=1)
        return SmtpMail(mail_server, from_address, logger, send_to)

    if implementation == "fs":
        output = config.get("email-fs", "output_path", fallback="output")
        return FsMail(from_address, logger, pathlib.Path(output).resolve())


@dataclass
class Settings:
    """Stores and parses configuration the settings INI file.

    Some values are lazy-loaded from functions (instead of properties) because
    they may have side-effects, such as connecting to an SMTP server.
    """

    source: Any
    worker: Any
    bugzilla_host: str
    logger: Logger
    sentry_dsn: str
    db_url: str
    _config: ConfigParser

    def __init__(self, config: ConfigParser):
        logger = _parse_logger(config)
        source, worker = _parse_pipeline(config, logger)
        self.source = source
        self.worker = worker
        self.bugzilla_host = config.get("bugzilla", "host")
        self.logger = logger
        self.sentry_dsn = config.get("sentry", "dsn", fallback="")
        self.db_url = config.get("db", "url")
        self._config = config

    def db(self):
        return DB(create_engine(self.db_url))

    def mail(self):
        return _parse_mail(self._config, self.logger)

    @classmethod
    def load(cls):
        """Load and parse settings from a settings.ini file in the package directory."""

        config = configparser.ConfigParser()
        # The location of "settings.ini" cannot be parameterized because alembic
        # needs access to the db connection string, but can't have access to
        # CLI parameters. So, our most usable option is to require that "settings.ini"
        # is in the package directory.
        path = pathlib.Path(PACKAGE_DIRECTORY / "settings.ini").resolve()
        if not config.read(str(path)):
            raise Exception(f'No config file found at "{path}"')

        return cls(config)