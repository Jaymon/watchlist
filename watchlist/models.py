# -*- coding: utf-8 -*-
from __future__ import unicode_literals, division, print_function, absolute_import
import os

from prom import Orm, Field, DumpField, Index
import sendgrid
from bs4 import BeautifulSoup

from .email import Email as BaseEmail
from .compat import *


class Email(BaseEmail):
    @property
    def subject(self):
        fmt_str = "{cheaper_count} down, {richer_count} up [wishlist {name}]"
        fmt_args = {
            "cheaper_count": len(self.cheaper_items),
            "richer_count": len(self.richer_items),
            "name": self.name
        }

        item_count = self.kwargs.get("item_count", 0)
        if item_count:
            fmt_str = "{cheaper_count} down, {richer_count} up, {item_count} total [wishlist {name}]"
            fmt_args["item_count"] = item_count

        return fmt_str.format(**fmt_args)

    @property
    def body_html(self):
        lines = []
        if self.cheaper_items:
            lines.append("<h2>Lower Priced</h2>")
            self.cheaper_items.sort(key=lambda ei: ei.new_item.price)
            for ei in self.cheaper_items:
                lines.append("{}".format(ei))
                lines.append("<hr>")

        if self.richer_items:
            lines.append("<h2>Higher Priced</h2>")
            self.richer_items.sort(key=lambda ei: ei.new_item.price)
            for ei in self.richer_items:
                lines.append("{}".format(ei))
                lines.append("<hr>")

        if self.nostock_items:
            lines.append("<h2>Out of Stock</h2>")
            self.nostock_items.sort(key=lambda ei: ei.old_item.price)
            for ei in self.nostock_items:
                lines.append("{}".format(ei))
                lines.append("<hr>")

        return "\n".join(lines)

    def __init__(self, name):
        self.name = name
        self.kwargs = {}
        self.cheaper_items = []
        self.richer_items = []
        self.nostock_items = []

    def append(self, old_item, new_item, cheapest_item=None):
        ei = EmailItem(old_item, new_item, cheapest_item)
        if ei.is_richer():
            self.richer_items.append(ei)
        elif ei.is_stocked():
            self.cheaper_items.append(ei)
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
    def __init__(self, old_item, new_item, cheapest_item=None):
        self.old_item = old_item
        self.new_item = new_item
        self.cheapest_item = cheapest_item

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
            lines.append("    <p>Lowest price was <b>${:.2f}</b> on {}</p>".format(
                citem.body.get("price", 0.0),
                citem._created.strftime("%Y-%m-%d")
            ))

        lines.extend([
            "    <p>{}</p>".format(new_item.body.get("comment", "")),
            "  </td>",
            "</tr>",
            "</table>",
        ])

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


class Item(Orm):

    table_name = "watchlist_item"
    connection_name = "watchlist"

    uuid = Field(str, True, max_size=32)
    price = Field(int, True)
    body = DumpField(True)

    @classmethod
    def cheapest(cls, uuid):
        return cls.query.is_uuid(uuid).gt_price(0).asc_price().get_one()

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

    def is_digital(self):
        """Returns True if this is a digital item like a Kindle book or mp3"""
        return self.body.get("digital", False)

    def is_stocked(self):
        """Return True if the item is in stock"""
        return self.price or self.is_digital()

