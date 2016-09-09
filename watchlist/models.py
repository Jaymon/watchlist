from __future__ import unicode_literals
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
        lines.append("<h2>Lower Priced</h2>")
        self.cheaper_items.sort(key=lambda ei: ei.new_item.price)
        for ei in self.cheaper_items:
            lines.append("{}".format(ei))
            lines.append("<hr>")

        lines.append("<h2>Higher Priced</h2>")
        self.richer_items.sort(key=lambda ei: ei.new_item.price)
        for ei in self.richer_items:
            lines.append("{}".format(ei))
            lines.append("<hr>")

        return "\n".join(lines)

    def __init__(self, name):
        self.name = name
        self.kwargs = {}
        self.cheaper_items = []
        self.richer_items = []

    def append(self, old_item, new_item):
        if old_item.price < new_item.price:
            self.richer_items.append(EmailItem(old_item, new_item))
        else:
            self.cheaper_items.append(EmailItem(old_item, new_item))

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

    def __unicode__(self):
        old_item = self.old_item
        new_item = self.new_item

        url = new_item.body["url"]
        lines = [
            "<table>",
            "<tr>",
            "  <td><a href=\"{}\"><img src=\"{}\"></a></td>".format(
                url,
                new_item.body["image"]
            ),
            "  <td>"
            "    <h3><a href=\"{}\">{}</a></h3>".format(
                url,
                new_item.body["title"]
            ),
            "    <p>is now ${} ({}), previously was ${} ({})</p>".format(
                new_item.body["price"],
                new_item.price,
                old_item.body["price"],
                old_item.price
            ),
            "    <p>{}</p>".format(new_item.body.get("comment", "")),
            "  </td>",
            "</tr>",
            "</table>",
        ]

        return "\n".join(lines)

    def __str__(self):
        if is_py3:
            return self.__unicode__()
        else:
            return self.__unicode__().encode("utf8")


class Item(Orm):

    table_name = "watchlist_item"
    connection_name = "watchlist"

    uuid = Field(str, True, max_size=32)
    price = Field(int, True)
    body = DumpField(True)

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

