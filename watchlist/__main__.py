# -*- coding: utf-8 -*-
from __future__ import unicode_literals, division, print_function, absolute_import
import sys
import traceback
import time
import random
import logging
import sys
import datetime


# configure logging, for debugging
logger = logging.getLogger()
logger.setLevel(logging.WARNING)
log_handler = logging.StreamHandler(stream=sys.stderr)
log_formatter = logging.Formatter('[%(levelname).1s|%(asctime)s|%(filename)s:%(lineno)s] %(message)s')
log_handler.setFormatter(log_formatter)
logger.addHandler(log_handler)
# turn off certain logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
#pl = logging.getLogger('prom')
#pl.setLevel(logging.CRITICAL)


from captain import echo, exit as console, ArgError
from captain.decorators import arg, args
from wishlist.core import Wishlist, RobotError

from watchlist import __version__
from watchlist.models import Email, Item
from watchlist.email import Email as ErrorEmail


@arg('name', nargs=1, help="the name of the wishlist, amazon.com/gp/registry/wishlist/NAME")
@arg('--dry-run', dest="dry_run", action="store_true", help="Perform a dry run")
def main(name, dry_run):
    """go through and check wishlist against previous entries"""
    name = name[0]
    email = Email(name)
    errors = []
    item_count = 1
    try:
        try:
            w = Wishlist(name)
            for item_count, wi in enumerate(w, item_count):
                try:
                    new_item = Item(
                        uuid=wi.uuid,
                        body=wi.jsonable(),
                        price=wi.price
                    )

                    echo.out("{}. {}", item_count, wi.title)

                    old_item = Item.query.is_uuid(wi.uuid).last()
                    if old_item:
                        if new_item.price != old_item.price:
                            cheapest_item = Item.cheapest(new_item.uuid)
                            email.append(old_item, new_item, cheapest_item)
                            if not dry_run:
                                new_item.save()
                            echo.indent("price has changed from {} to {}".format(
                                new_item.price,
                                old_item.price
                            ))

                    else:
                        echo.indent("This is a new item")
                        if not dry_run:
                            new_item.save()

                except RobotError:
                    raise

                except Exception as e:
                    exc_type, exc_value, exc_traceback = sys.exc_info()
                    errors.append((e, (exc_type, exc_value, exc_traceback)))

                    echo.err("{}. Failed!", item_count)
                    echo.exception(e)

            echo.out(
                "{}. Done with wishlist, {} total items, {} changes",
                datetime.datetime.utcnow(),
                item_count,
                len(email),
            )

        except Exception as e:
            exc_type, exc_value, exc_traceback = sys.exc_info()
            errors.append((e, (exc_type, exc_value, exc_traceback)))
            echo.exception(e)

        if not dry_run:
            if errors:
                subject = "{} errors raised".format(len(errors))
                echo.err(subject)
                em = ErrorEmail()
                em.subject = subject
                body = []

                for e, sys_exc_info in errors:
                    exc_type, exc_value, exc_traceback = sys_exc_info
                    stacktrace = traceback.format_exception(exc_type, exc_value, exc_traceback)
                    body.append(e.message)
                    body.append("".join(stacktrace))
                    body.append("")

                em.body_text = "\n".join(body)
                em.send()

            email.send(item_count=item_count)

    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    console()

