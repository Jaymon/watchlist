# -*- coding: utf-8 -*-
from __future__ import unicode_literals, division, print_function, absolute_import
import os

from prom import Orm, Field, ObjectField, Index
import sendgrid
from bs4 import BeautifulSoup

from .email import Email as BaseEmail
from .compat import *


class Email(BaseEmail):
    @property
    def subject(self):
        fmt_args = {
            "cheaper_count": len(self.cheaper_items),
            "cheapest_count": len(self.cheapest_items),
            "richer_count": len(self.richer_items),
            "name": self.name
        }

        fmt_str = [
            "{cheaper_count} down,",
            "{cheapest_count} cheapest,",
            "{richer_count} up,", 
        ]

        item_count = self.kwargs.get("item_count", 0)
        if item_count:
            fmt_str.append("{item_count} total")
            fmt_args["item_count"] = item_count

        fmt_str.append("[wishlist {name}]")
        return " ".join(fmt_str).format(**fmt_args)

    @property
    def body_html(self):
        lines = []
        if self.cheaper_items:
            lines.append("<h2>Lower Priced</h2>")
            self.cheaper_items.sort(key=lambda ei: ei.new_item.price)
            for ei in self.cheaper_items:
                lines.append("{}".format(ei))

        if self.richer_items:
            lines.append("<h2>Higher Priced</h2>")
            self.richer_items.sort(key=lambda ei: ei.new_item.price)
            for ei in self.richer_items:
                lines.append("{}".format(ei))

        if self.cheapest_items:
            lines.append("<h2>Cheapest</h2>")
            self.cheapest_items.sort(key=lambda ei: ei.new_item.price)
            for ei in self.cheapest_items:
                lines.append("{}".format(ei))

        if self.nostock_items:
            lines.append("<h2>Out of Stock</h2>")
            self.nostock_items.sort(key=lambda ei: ei.old_item.price)
            for ei in self.nostock_items:
                lines.append("{}".format(ei))

        return "\n".join(lines)

    def __init__(self, name):
        self.name = name
        self.kwargs = {}
        self.cheaper_items = []
        self.cheapest_items = []
        self.richer_items = []
        self.nostock_items = []

    def append(self, old_item, new_item):
        ei = EmailItem(old_item, new_item)
        if ei.is_richer():
            self.richer_items.append(ei)
        elif ei.is_stocked():
            self.cheaper_items.append(ei)
        elif ei.is_cheapest():
            self.cheapest_items.append(ei)
        else:
            self.nostock_items.append(ei)

    def __len__(self):
        return len(self.cheaper_items) + len(self.richer_items)

    def __nonzero__(self): return self.__bool__() # 2
    def __bool__(self):
        return len(self) > 0

    def send(self, **kwargs):
        if not self: return None
        self.kwargs.update(kwargs)
        return super(Email, self).send()


class EmailItem(object):
    def __init__(self, old_item, new_item):
        self.old_item = old_item
        self.new_item = new_item
        self.cheapest_item = new_item.cheapest
        self.richest_item = new_item.richest

    def __unicode__(self):
        old_item = self.old_item
        new_item = self.new_item

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

        if self.is_cheapest():
            lines.append(
                "    <h3><a style=\"color:green\" href=\"{}\">{}</a></h3>".format(
                    url,
                    new_item.body["title"]
                )
            )

        elif self.is_richest():
            lines.append(
                "    <h3><a style=\"color:red\" href=\"{}\">{}</a></h3>".format(
                    url,
                    new_item.body["title"]
                )
            )

        else:
            lines.append(
                "    <h3><a href=\"{}\">{}</a></h3>".format(
                    url,
                    new_item.body["title"]
                )
            )

        lines.append(
            "    <p><b>${:.2f}</b>, previously was <b>${:.2f}</b></p>".format(
                new_item.body["price"],
                old_item.body["price"],
            )
        )

        if new_item.is_digital():
            lines.append(
                "    <p>This is a digital item</p>"
            )

        if self.cheapest_item:
            citem = self.cheapest_item
            lines.append("    <p>Lowest price was <b>${:.2f}</b> on {} ({} times total)</p>".format(
                citem.body.get("price", 0.0),
                citem._created.strftime("%Y-%m-%d"),
                citem.price_count,
            ))

        added = new_item.body.get("added", None)
        page_url = new_item.body.get("page_url", "")
        if page_url and added:
            lines.append("    <p><a href=\"{}\">page</a>, added {}</p>".format(
                added,
                page_url
            ))

        lines.extend([
            "    <p>{}</p>".format(new_item.body.get("comment", "")),
            "  </td>",
            "</tr>",
            "</table>",
        ])

        lines.append("<hr>")

        return "\n".join(lines)

    def __str__(self):
        if is_py3:
            return self.__unicode__()
        else:
            return self.__unicode__().encode("UTF-8")

    def is_richer(self):
        """Return true if the new item is more expensive than the old item"""
        return self.old_item.price < self.new_item.price

    def is_stocked(self):
        """Return True if the item is in stock"""
        return self.new_item.is_stocked()

    def is_cheapest(self):
        """Return True if the item is the cheapest it's ever been"""
        ret = False
        if not self.is_richer():
            if self.cheapest_item:
                ret = self.new_item.price == self.cheapest_item.price
        return ret

    def is_richest(self):
        """Return True if the item is the richest it's ever been"""
        ret = False
        if self.is_richer():
            if self.richest_item:
                ret = self.new_item.price == self.richest_item.price
        return ret


class Item(Orm):

    table_name = "watchlist_item"
    connection_name = "watchlist"

    uuid = Field(str, True, max_size=32)
    price = Field(int, True)
    body = ObjectField(True)

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
    def cheapest(self):
        """Return the cheapest record of this item in the db"""
        return self.query.is_uuid(self.uuid).gt_price(0).asc_price().get_one()

    @property
    def richest(self):
        """Return the richest record of this item in the db"""
        return self.query.is_uuid(self.uuid).gt_price(0).desc_price().get_one()

    @property
    def last(self):
        """Return the most recent record of this item in the db"""
        return self.query.is_uuid(self.uuid).last()

    @property
    def price_count(self):
        """how many times this price has been seen"""
        return self.query.is_uuid(self.uuid).is_price(self.price).count()

    def is_digital(self):
        """Returns True if this is a digital item like a Kindle book or mp3"""
        return self.body.get("digital", False)

    def is_stocked(self):
        """Return True if the item is in stock"""
        return self.price or self.is_digital()

