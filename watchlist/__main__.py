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
from wishlist import Wishlist
from wishlist.exception import RobotError

from watchlist import __version__
from watchlist.models import Email, Item, WatchlistItem
from watchlist.email import Email as ErrorEmail


@arg('name', nargs=1, help="the name of the wishlist, amazon.com/gp/registry/wishlist/NAME")
@arg('--dry-run', dest="dry_run", action="store_true", help="Perform a dry run")
def main(name, dry_run):
    """go through and check wishlist against previous entries"""

    echo.out(
        "{}. Starting on wishlist {}",
        datetime.datetime.utcnow(),
        name,
    )

    name = name[0]
    email = Email(name)
    errors = []
    item_count = 1
    try:
        try:

            # Let's flush out any problems connecting to the DB before getting into
            # the loop
            WatchlistItem.interface.connect()

            w = Wishlist(name)
            for item_count, we in enumerate(w, item_count):
                try:
                    echo.out("{}. (p{}) {}", item_count, we.page, we.title)

                    item = Item(
                        uuid=we.uuid,
                        body=we.jsonable(),
                        price=we.price,
                        element=we,
                    )

                    if item.is_newest():
                        echo.indent("This is a new item")
                        if not dry_run:
                            item.save()

                    else:
                        if item.is_richer():
                            email.richer_items.append(item)
                            echo.indent("price has gone up from {} to {}".format(
                                item.last.price,
                                item.newest.price,
                            ))
                            if not dry_run:
                                item.save()

                        elif item.is_cheaper():
                            email.cheaper_items.append(item)
                            echo.indent("price has gone down from {} to {}".format(
                                item.last.price,
                                item.newest.price,
                            ))
                            if not dry_run:
                                item.save()

                        elif item.is_cheapest():
                            email.cheapest_items.append(item)
                            echo.indent("price is as cheap as it has ever been {}".format(
                                item.newest.price,
                            ))

                        elif not item.is_stocked():
                            email.nostock_items.append(item)
                            echo.indent("is out of stock")

                except RobotError:
                    raise

                except Exception as e:
                    exc_type, exc_value, exc_traceback = sys.exc_info()
                    errors.append((e, (exc_type, exc_value, exc_traceback)))

                    echo.err("{}. Failed!", item_count)
                    echo.exception(e)

                    # bail if we've had a lot of errors or the first N items
                    # have all resulted in an error
                    total_errors = len(errors)
                    if total_errors > 100 or (total_errors > 10 and total_errors == item_count):
                        break

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
                    body.append(str(e))
                    body.append("".join(stacktrace))
                    body.append("")

                em.body_text = "\n".join(body)
                em.send()

            email.send(item_count=item_count)

    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    console()

