from __future__ import unicode_literals
import sys
import traceback
import time
import random
import logging
import sys

from captain import echo, exit as console, ArgError
from captain.decorators import arg, args
from wishlist.core import Wishlist
from wishlist.browser import RecoverableCrash

from watchlist import __version__
from watchlist.models import Email, Item
from watchlist.email import Email as ErrorEmail


# configure logging, for debugging
logger = logging.getLogger()
logger.setLevel(logging.DEBUG)
log_handler = logging.StreamHandler(stream=sys.stderr)
log_formatter = logging.Formatter('[%(levelname)s] %(message)s')
log_handler.setFormatter(log_formatter)
logger.addHandler(log_handler)


@arg('name', help="the name of the wishlist")
@arg('--page', dest="current_page", type=int, default=0, help="The Wishlist page you want to start on")
def main(name, current_page):
    """go through and check wishlist against previous entries"""

    email = Email(name)
    errors = []
    item_count = 1
    try:
        try:
            w = Wishlist()
            for item_count, wi in enumerate(w.get(name, current_page), item_count):
                try:
                    new_item = Item(
                        uuid=wi.uuid,
                        body=wi.jsonable(),
                        price=wi.price
                    )

                    #if not new_item.price:
                    #    new_item.price = wi.marketplace_price

                    echo.out("{}. {}", item_count, wi.title)

                    old_item = Item.query.is_uuid(wi.uuid).last()
                    if old_item:
                        if new_item.price != old_item.price:
                            email.append(old_item, new_item)
                            new_item.save()
                            echo.indent("price has changed from {} to {}".format(
                                new_item.price,
                                old_item.price
                            ))

                    else:
                        # we haven't seen this item previously
                        new_item.save()
                        echo.indent("this is a new item")

                except Exception as e:
                    exc_type, exc_value, exc_traceback = sys.exc_info()
                    errors.append((e, (exc_type, exc_value, exc_traceback)))

                    echo.err("{}. Failed!", item_count)
                    echo.exception(e)

                finally:
                    current_page = w.current_page

            echo.out("Done with wishlist, {} total pages", current_page)

        except Exception as e:
            exc_type, exc_value, exc_traceback = sys.exc_info()
            errors.append((e, (exc_type, exc_value, exc_traceback)))
            echo.exception(e)

        if errors:
            em = ErrorEmail()
            em.subject = "{} errors raised".format(len(errors))
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

