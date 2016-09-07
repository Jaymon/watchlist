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
def main(name):
    """go through and check wishlist against previous entries"""

    errors = []
    try:
        with Wishlist.lifecycle() as w:
            email = Email(name)

            for i, wi in enumerate(w.get(name), 1):
                try:
                    new_item = Item(
                        uuid=wi.uuid,
                        body=wi.jsonable(),
                        price=wi.price
                    )

                    if not new_item.price:
                        new_item.price = wi.marketplace_price

                    echo.out("{}. {}", i, wi.title)

                    old_item = Item.query.is_uuid(wi.uuid).last()
                    if old_item:
                        if new_item.price < old_item.price:
                            echo.indent("price has gone down to {}", new_item.body.price)
                            email.append(old_item, new_item)

                        elif new_item.price > old_item.price:
                            echo.indent("price has gone up to {}", new_item.body.price)
                            email.append(old_item, new_item)

                    else:
                        # we haven't seen this item previously
                        echo.indent("this is a new item")
                        new_item.save()

                except Exception as e:
                    exc_type, exc_value, exc_traceback = sys.exc_info()
                    errors.append((e, (exc_type, exc_value, exc_traceback)))

                    echo.err("{}. Failed!", i)
                    echo.exception(e)

                if (i % 25) == 0:
                    sleep_count = random.randint(1, 5)
                    echo.h3("Sleeping for {} seconds".format(sleep_count))
                    time.sleep(sleep_count)

            email.send()

    except Exception as e:
        exc_type, exc_value, exc_traceback = sys.exc_info()
        errors.append((e, (exc_type, exc_value, exc_traceback)))
        echo.exception(e)

    finally:
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


if __name__ == "__main__":
    console()

