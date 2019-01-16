# -*- coding: utf-8 -*-
from __future__ import unicode_literals, division, print_function, absolute_import
import os
import datetime
import bisect
from distutils import dir_util
import codecs
import logging

from prom import Orm, Field, ObjectField, Index
import sendgrid
from bs4 import BeautifulSoup

from .email import Email as BaseEmail, ErrorEmail
from .compat import *
from . import environ


logger = logging.getLogger(__name__)


class Filepath(object):
    @property
    def directory(self):
        return os.path.dirname(self.path)

    def __init__(self, *bits):
        self.path = os.path.join(*bits)
        self.encoding = "UTF-8"

    def write(self, contents):
        dir_util.mkpath(self.directory)
        with self.open("w+") as f:
            return f.write(contents)

    def open(self, mode=""):
        if not mode:
            mode = "r"
        return codecs.open(self.path, encoding=self.encoding, mode=mode)


class SortedList(list):
    """Keep a list sorted as you append or extend it

    simpler version of this recipe:
        https://code.activestate.com/recipes/577197-sortedcollection/

    uses this stdlib:
        https://docs.python.org/2.7/library/bisect.html
    """
    def __init__(self, key=None, reverse=False):
        self.key = (lambda x: x) if key is None else key
        self.reverse = reverse
        self.semaphore = False
        self._keys = []

    def append(self, x):
        k = self.key(x)
        i = bisect.bisect_right(self._keys, k)
        self.semaphore = True
        if i is None:
            super(SortedList, self).append(x)
            self._keys.append(k)
        else:
            self.insert(i, x)
            self._keys.insert(i, k)
        self.semaphore = False

    def extend(self, iterable):
        for x in iterable:
            self.append(x)

    def insert(self, i, x):
        if self.semaphore:
            super(SortedList, self).insert(i, x)
        else:
            raise NotImplementedError()

    def remove(self, x):
        k = self.key(x)
        self._keys.remove(k)
        super(SortedList, self).remove(x)

    def pop(self, *args, **kwargs):
        super(SortedList, self).pop(*args, **kwargs)
        self._keys.pop(*args, **kwargs)

    def clear(self):
        super(SortedList, self).clear()
        self._keys.clear()

    def __getitem__(self, i):
        if self.reverse:
            i = -(i + 1)
        return super(SortedList, self).__getitem__(i)

    def __iter__(self):
        if self.reverse:
            for x in reversed(self):
                yield x
        else:
            for x in super(SortedList, self).__iter__():
                yield x

    def __setitem__(self, x):
        raise NotImplementedError()
    def reverse(self):
        raise NotImplementedError()
    def sort(self):
        raise NotImplementedError()


class Email(BaseEmail):
    @property
    def subject(self):
        fmt_args = {
            "cheaper_count": len(self.cheaper_items),
            "cheaper_start_price": self.cheaper_items[0].current_pricetag,
            "cheaper_stop_price": self.cheaper_items[-1].current_pricetag,
            "name": self.name
        }

        item_count = self.kwargs.get("item_count", 0)
        if item_count:
            fmt_str = [
                "{cheaper_count}/{item_count} down,"
            ]
            fmt_args["item_count"] = item_count

        else:
            fmt_str = [
                "{cheaper_count} down,"
            ]

        fmt_str.append("{cheaper_start_price}-{cheaper_stop_price}")

        fmt_str.append("[wishlist {name}]")
        return " ".join(fmt_str).format(**fmt_args)

    @property
    def body_html(self):
        lines = ["<p>"]

        fmt_args = {
            "cheaper_count": len(self.cheaper_items),
            "cheapest_count": len(self.cheapest_items),
            "richer_count": len(self.richer_items),
            "name": self.name,
            "date": datetime.datetime.now().date().strftime("%Y-%m-%d"),
        }

        fmt_str = [
            "{date}:",
            "{cheaper_count} down,",
            "{cheapest_count} cheapest,",
            "{richer_count} up",
        ]

        item_count = self.kwargs.get("item_count", 0)
        if item_count:
            fmt_str.append("{item_count} total")
            fmt_args["item_count"] = item_count

        lines.append(" ".join(fmt_str).format(**fmt_args))
        lines.append("</p>")

        if self.cheaper_items:
            lines.append("<h2>Lower Priced</h2>")
            #self.cheaper_items.sort(key=lambda i: i.newest.price)
            for i in self.cheaper_items:
                lines.append(i.html_detail())

        return "\n".join(lines)

    @property
    def html(self):
        """the full html for like a website, not an email"""
        try:
            title = self.subject
        except IndexError:
            title = ""

        lines = [self.body_html]
        if self.richer_items:
            lines.append("<h2>Higher Priced</h2>")
            #self.richer_items.sort(key=lambda i: i.newest.price)
            for i in self.richer_items:
                lines.append(i.html_summary())

        if self.cheapest_items:
            lines.append("<h2>Cheapest</h2>")
            for i in self.cheapest_items:
                lines.append(i.html_summary())

        if self.nostock_items:
            lines.append("<h2>Out of Stock</h2>")
            #self.nostock_items.sort(key=lambda i: i.last.price if i.last else 0)
            for i in self.nostock_items:
                lines.append(i.html_summary())

        body = "\n".join(lines)

        return "\n".join([
            "<!DOCTYPE html>",
            "<html>",
            "<head>",
            '<meta charset="utf-8" />',
            "<title>{}</title>".format(title),
            '<meta name="viewport" content="width=device-width, initial-scale=1.0, user-scalable=no" />',
            "</head>",
            "<body>",
            "<h1>{}</h1>".format(title),
            "<div>{}</div>".format(body),
            "</body>",
            "</html>",
        ])

    def __init__(self, name):
        self.name = name
        self.kwargs = {}
        self.cheaper_items = SortedList(key=lambda i: i.newest.price)
        self.richer_items = SortedList(key=lambda i: i.newest.price)
        self.nostock_items = SortedList(key=lambda i: i.last.price if i.last else 0)
        self.errors = []

        def sorting(i):
            ci = i.cheapest
            return ci._created if ci else datetime.datetime.utcnow()
        self.cheapest_items = SortedList(key=sorting)

    def __len__(self):
        return len(self.cheaper_items) + len(self.richer_items) + len(self.cheapest_items)

    def __bool__(self):
        return len(self) > 0
    __nonzero__ = __bool__ # 2

    def send(self, **kwargs):
        if self.errors:
            logger.warning("There were {} errors".format(len(self.errors)))
            try:
                em = ErrorEmail(self.errors)

                if environ.ERROR_PATH:
                    fp = Filepath(environ.ERROR_PATH)
                    fp.write(em.body_text)
                em.send()

            except Exception as e:
                logger.exception(e)

        if self:
            self.kwargs.update(kwargs)
            if environ.SUCCESS_PATH:
                fp = Filepath(environ.SUCCESS_PATH)
                fp.write(self.html)
            logger.warning("Sending successful email to {}".format(self.to_email))
            return super(Email, self).send()


class WatchlistItem(Orm):
    """This represents one single price point of the item, anytime the price of the
    item changes there will be a new row that is represented by this class

    if you want to look at the item as a whole (all its price changes) then you
    would use the Item class
    """
    table_name = "watchlist_item"
    connection_name = "watchlist"

    uuid = Field(str, True, max_size=32)
    price = Field(int, True)
    body = ObjectField(True)

    uuid_index = Index("uuid", "price")

    def _modify(self, fields):
        if "body" in fields:
            if "price" in fields:
                fields["body"].setdefault("price", fields["price"])
            if "uuid" in fields:
                fields["body"].setdefault("uuid", fields["uuid"])
        return fields

    @body.fsetter
    def body(self, val):
        if val is None: return None
        if self.uuid is None:
            self.uuid = val.get("uuid", None)
        if self.price is None:
            self.price = val.get("price", None)
        return val

    @price.fsetter
    def price(self, val):
        """make sure price is in cents"""
        if val is None: return None
        if isinstance(val, (int, long)): return val
        return int(val * 100.0)

    @property
    def price_count(self):
        """how many times this price has been seen"""
        return self.query.is_uuid(self.uuid).is_price(self.price).count()

    @property
    def count(self):
        """how many total price changes there have been"""
        return self.query.is_uuid(self.uuid).count()

    @property
    def pricetag(self):
        """it's price formatted in dollars and cents (so price=100 would be pricetag $1.00)"""
        price = self.body.get("price", 0.0)
        pricetag = "${:.2f}".format(price)
        return pricetag

    def __eq__(self, other):
        """Defines behavior for the equality operator, ==."""
        return self.price == other.price

    def __ne__(self, other):
        """Defines behavior for the inequality operator, !=."""
        return self.price != other.price

    def __lt__(self, other):
        """Defines behavior for the less-than operator, <."""
        return self.price < other.price

    def __gt__(self, other):
        """Defines behavior for the greater-than operator, >."""
        return self.price > other.price

    def __le__(self, other):
        """Defines behavior for the less-than-or-equal-to operator, <=."""
        return self.price <= other.price

    def __ge__(self, other):
        """Defines behavior for the greater-than-or-equal-to operator, >=."""
        return self.price >= other.price


class Item(object):
    """Represents the item as a whole, its entire price history, this is the public
    interface that takes the information from a wishlist item and converts it into
    a watchlist item"""
    @property
    def current_price(self):
        return self.newest.price

    @property
    def current_pricetag(self):
        return self.newest.pricetag

    @property
    def title(self):
        title = self.newest.body["title"]
        if self.is_digital():
            title += " (digital)"
        return title

    @property
    def color(self):
        """return a different color depending on if the item is cheapest, richest,
        or somewhere in the middle"""
        color = "black"
        if self.is_cheapest():
            color = "green"

        elif self.is_richest():
            color = "red"
        return color

    @property
    def uuid(self):
        return self.newest.uuid

    @property
    def cheapest(self):
        """Return the cheapest record of this item in the db"""
        ret = WatchlistItem.query.is_uuid(self.uuid).gt_price(0).asc_price().get_one()
        self.__dict__["cheapest"] = ret
        return ret

    @property
    def richest(self):
        """Return the richest record of this item in the db"""
        ret = WatchlistItem.query.is_uuid(self.uuid).gt_price(0).desc_price().get_one()
        self.__dict__["richest"] = ret
        return ret

    @property
    def last(self):
        """Return the most recent record of this item in the db"""
        if self.newest.pk:
            ret = WatchlistItem.query.is_uuid(self.uuid).lt_pk(self.newest.pk).desc_pk().first()
        else:
            ret = WatchlistItem.query.is_uuid(self.uuid).last()
        self.__dict__["last"] = ret
        return ret

    def __init__(self, uuid, body, price, element=None, **kwargs):
        """
        :param uuid: string, the amazon uuid of the item
        :param body: dict, the wishlist element jsonable
        :param price: number, the price of the item
        :param item: the original wishlist.WishlistElement instance
        """
        self.newest = WatchlistItem(
            uuid=uuid,
            body=body,
            price=price,
            **kwargs
        )

        # NOTE: we CANNOT save the element because it will cause a memory leak
        # with big wishlists, so just save the things you want from the element
        # right here
        #self.element = element
        self.page = element.page if element else 0


    def is_richer(self):
        """Return true if the new item is more expensive than the old item"""
        if not self.is_stocked(): return False
        last = self.last
        return last is not None and last.price < self.newest.price

    def is_cheaper(self):
        if not self.is_stocked(): return False
        ret = False
        last = self.last
        if last:
            ret = self.newest.price < last.price
        return ret

    def is_stocked(self):
        """Return True if the item is in stock"""
        return self.newest.price or self.is_digital()

    def is_digital(self):
        """Returns True if this is a digital item like a Kindle book or mp3"""
        return self.newest.body.get("digital", False)

    def is_cheapest(self):
        """Return True if the item is the cheapest it's ever been"""
        ret = False
        if not self.is_richer() and self.is_stocked():
            if self.cheapest:
                ret = self.newest.price <= self.cheapest.price
            else:
                ret = True # no other one exists in db
        return ret

    def is_richest(self):
        """Return True if the item is the richest it's ever been"""
        ret = False
        if self.is_stocked():
            if self.richest:
                ret = self.newest.price >= self.richest.price
            else:
                ret = True # no other one exists in db
        return ret

    def is_newest(self):
        """Return if there are no other items like this one in the db"""
        return not WatchlistItem.query.is_uuid(self.uuid).has()

    def save(self):
        return self.newest.save()

    def html_detail(self):
        item = self
        new_item = self.newest
        old_item = self.last
        citem = self.cheapest
        ritem = self.richest

        url = new_item.body["url"]

        lines = [
            "<table>",
            "<tr>",
        ]

        image_url = new_item.body.get("image", "")
        if image_url:
            lines.extend([
                "  <td>",
                "    <a href=\"{}\"><img src=\"{}\"></a>".format(
                    url,
                    image_url
                ),
                "  </td>",
            ])

        lines.append(
            "  <td>"
        )

        title = self.title
        color = self.color
        lines.append("    <h3><a style=\"color:{}\" href=\"{}\">{}</a></h3>".format(
            color,
            url,
            title
        ))

        lines.append("    <p>")
        lines.append("        <b>{}</b>".format(new_item.pricetag))
        if old_item:
            lines.append("        was <b>{}</b></p>".format(
                old_item.pricetag,
            ))
        lines.append("    </p>")

        if citem and ritem:
            format_str = "    <p>range: <b>{}</b> ({}x, last on {}) to <b>{}</b> ({}x), {}x total changes</p>"
            lines.append(format_str.format(
                citem.pricetag,
                citem.price_count,
                citem._created.strftime("%B %d, %Y"),
                ritem.pricetag,
                ritem.price_count,
                ritem.count,
            ))

        lines.append("    <p>")
        page_url = new_item.body.get("page_url", "")
        added = new_item.body.get("added", "unknown")
        if page_url:
            lines.append("        <a href=\"{}\">added {}, p{}</a>".format(page_url, added, self.page))

        else:
            lines.append("        added {}".format(added))

        lines.append("    </p>")

        lines.extend([
            "    <p>{}</p>".format(new_item.body.get("comment", "")),
            "  </td>",
            "</tr>",
            "</table>",
        ])

        lines.append("<hr>")

        return "\n".join(lines)

    def html_summary(self):
        lines = ["<p>"]

        item = self
        new_item = self.newest
        old_item = self.last
        citem = self.cheapest
        ritem = self.richest

        url = new_item.body["url"]

        title = self.title
        color = self.color
        lines.append("    <a style=\"color:{}\" href=\"{}\">{}</a>".format(
            color,
            url,
            title
        ))

        if citem and ritem:
            if citem < new_item < ritem:
                lines.append("    {} < <b>{}</b> < {}".format(citem.pricetag, new_item.pricetag, ritem.pricetag))
            elif citem == new_item:
                lines.append("    <b>{}</b> < {}".format(new_item.pricetag, ritem.pricetag))
            else:
                lines.append("    {} < <b>{}</b>".format(citem.pricetag, new_item.pricetag))

        else:
            if old_item:
                if old_item < new_item:
                    lines.append("    {} < <b>{}</b>".format(old_item.pricetag, new_item.pricetag))
                elif old_item > new_item:
                    lines.append("    <b>{}</b> < {}".format(new_item.pricetag, old_item.pricetag))
                else:
                    lines.append("    <b>{}</b>".format(new_item.pricetag))
            else:
                lines.append("    <b>{}</b>".format(new_item.pricetag))

        page_url = new_item.body.get("page_url", "")
        added = new_item.body.get("added", "unknown")
        if page_url:
            lines.append("    (<a href=\"{}\">{}</a>)".format(page_url, added))

        else:
            lines.append("    (added {})".format(added))

        lines.append("</p>")
        return "\n".join(lines)


