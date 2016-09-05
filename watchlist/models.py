from __future__ import unicode_literals
import os

from prom import Orm, Field, DumpField, Index
import sendgrid
from bs4 import BeautifulSoup

from .email import Email as BaseEmail


class Email(BaseEmail):
    @property
    def subject(self):
        return "{} down, {} up [wishlist {}]".format(
            len(self.cheaper_items),
            len(self.richer_items),
            self.name
        )

    @property
    def body_html(self):
        lines = []
        lines.append("<h2>Lower Priced</h2>")
        for ei in self.cheaper_items:
            lines.append(str(ei))
            lines.append("<hr>")

        lines.append("<h2>Higher Priced</h2>")
        for ei in self.richer_items:
            lines.append(str(ei))
            lines.append("<hr>")

        return "\n".join(lines)

    def __init__(self, name):
        self.name = name
        self.cheaper_items = []
        self.richer_items = []

    def append(self, old_item, new_item):
        if old_item.price < new_item.price:
            self.richer_items.append(EmailItem(old_item, new_item))
        else:
            self.cheaper_items.append(EmailItem(old_item, new_item))

    def __len__(self):
        return len(self.cheaper_items) + len(self.richer_items)

    def __bool__(self):
        return len(self) > 0

    def send(self):
        if not self: return None
        return super(Email, self).send()


class EmailItem(object):
    def __init__(self, old_item, new_item):
        self.old_item = old_item
        self.new_item = new_item

    def __str__(self):
        old_item = self.old_item
        new_item = self.new_item
        lines = [
            "<table>",
            "<tr>",
            "  <td><a href=\"{}\"><img src=\"{}\"></a></td>".format(
                new_item.body["url"],
                new_item.body["image"]
            ),
            "  <td>"
            "    <h3><a href=\"{}\">{}</a></h3>".format(
                new_item.body["url"],
                new_item.body["title"]
            ),
            "    <p>is now {}, previously was {}</p>".format(
                old_item.body["price"],
                new_item.body["price"]
            ),
            "    <p>{}</p>".format(new_item.body.get("comment", "")),
            "  </td>",
            "</tr>",
            "</table>",
            #"<hr>",
        ]

        return "\n".join(lines)


class Item(Orm):

    table_name = "watchlist_item"
    connection_name = "watchlist"

    uuid = Field(str, True, max_size=32, unique=True)
    price = Field(int, True)
    body = DumpField(True)

    @price.fsetter
    def price(self, val):
        """make sure price is in cents"""
        if val is None: return None
        if isinstance(val, (int, long)): return val
        return int(val * 100.0)
