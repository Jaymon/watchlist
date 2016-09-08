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
    crash_count = 0
    max_crash_count = 10
    while crash_count < max_crash_count:
        try:
            with Wishlist.open() as w:

                for i, wi in enumerate(w.get(name, current_page), 1):
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
                                email.append(old_item, new_item)
                                echo.indent("price has gone down to {} from {}".format(
                                    new_item.price,
                                    old_item.price
                                ))

                            elif new_item.price > old_item.price:
                                email.append(old_item, new_item)
                                echo.indent("price has gone up to {} from {}".format(
                                    new_item.price,
                                    old_item.price
                                ))

                        else:
                            # we haven't seen this item previously
                            new_item.save()
                            echo.indent("this is a new item")

                    except KeyboardInterrupt:
                        raise

                    except Exception as e:
                        exc_type, exc_value, exc_traceback = sys.exc_info()
                        errors.append((e, (exc_type, exc_value, exc_traceback)))

                        echo.err("{}. Failed!", i)
                        echo.exception(e)

                    finally:
                        current_page = w.current_page

                    if (i % 25) == 0:
                        sleep_count = random.randint(1, 5)
                        echo.h3("Sleeping for {} seconds".format(sleep_count))
                        time.sleep(sleep_count)

        except KeyboardInterrupt:
            break

        except RecoverableCrash:
            crash_count += 1
            if crash_count > max_crash_count:
                raise

        except Exception as e:
            exc_type, exc_value, exc_traceback = sys.exc_info()
            errors.append((e, (exc_type, exc_value, exc_traceback)))
            echo.exception(e)

        else:
            echo.out("Done with wishlist, {} total pages", current_page)
            break

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

    email.send()

if __name__ == "__main__":
    console()

