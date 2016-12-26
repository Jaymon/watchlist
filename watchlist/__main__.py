from __future__ import unicode_literals
import sys
import traceback
import time
import random
import logging
import sys


# configure logging, for debugging
logger = logging.getLogger()
logger.setLevel(logging.DEBUG)
log_handler = logging.StreamHandler(stream=sys.stderr)
#log_formatter = logging.Formatter('[%(levelname)s] %(message)s')
log_formatter = logging.Formatter('[%(levelname)s] %(message)s [%(pathname)s:%(lineno)d]')
log_handler.setFormatter(log_formatter)
logger.addHandler(log_handler)


from captain import echo, exit as console, ArgError
from captain.decorators import arg, args
from wishlist.core import Wishlist, RobotError

from watchlist import __version__
from watchlist.models import Email, Item
from watchlist.email import Email as ErrorEmail


@arg('name', nargs=1, help="the name of the wishlist, amazon.com/gp/registry/wishlist/NAME")
@arg('--start-page', dest="start_page", type=int, default=1, help="The Wishlist page you want to start on")
@arg('--stop-page', dest="stop_page", type=int, default=0, help="The Wishlist page you want to stop on")
@arg('--dry-run', dest="dry_run", action="store_true", help="Perform a dry run")
def main(name, start_page, stop_page, dry_run):
    """go through and check wishlist against previous entries"""
    name = name[0]
    email = Email(name)
    errors = []
    item_count = 1
    current_page = 0
    try:
        try:
            w = Wishlist()
            for item_count, wi in enumerate(w.get(name, start_page, stop_page), item_count):
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
                            cheapest_item = Item.cheapest(new_item.uuid)
                            email.append(old_item, new_item, cheapest_item)
                            if not dry_run:
                                new_item.save()
                            echo.indent("price has changed from {} to {}".format(
                                new_item.price,
                                old_item.price
                            ))

                    else:
                        # we haven't seen this item previously
                        if not dry_run:
                            new_item.save()
                        echo.indent("this is a new item")

                except RobotError:
                    raise

                except Exception as e:
                    exc_type, exc_value, exc_traceback = sys.exc_info()
                    errors.append((e, (exc_type, exc_value, exc_traceback)))

                    echo.err("{}. Failed!", item_count)
                    echo.exception(e)

                finally:
                    current_page = w.current_page

            echo.out("Done with wishlist, {} total pages, {} items", current_page, item_count)

        except Exception as e:
            exc_type, exc_value, exc_traceback = sys.exc_info()
            errors.append((e, (exc_type, exc_value, exc_traceback)))
            echo.exception(e)

        if not dry_run:
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

