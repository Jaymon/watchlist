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
            self.cheaper_items.sort(key=lambda i: i.newest.price)
            for i in self.cheaper_items:
                lines.append("{}".format(i.email))

        if self.richer_items:
            lines.append("<h2>Higher Priced</h2>")
            self.richer_items.sort(key=lambda i: i.newest.price)
            for i in self.richer_items:
                lines.append("{}".format(i.email))

        if self.cheapest_items:
            lines.append("<h2>Cheapest</h2>")
            self.cheapest_items.sort(key=lambda i: i.newest.price)
            for i in self.cheapest_items:
                lines.append("{}".format(i.email))

        if self.nostock_items:
            lines.append("<h2>Out of Stock</h2>")
            self.nostock_items.sort(key=lambda i: i.last.price if i.last else 0)
            for i in self.nostock_items:
                lines.append("{}".format(i.email))

        return "\n".join(lines)

    def __init__(self, name):
        self.name = name
        self.kwargs = {}
        self.cheaper_items = []
        self.cheapest_items = []
        self.richer_items = []
        self.nostock_items = []

    def __len__(self):
        return len(self.cheaper_items) + len(self.richer_items) + len(self.cheapest_items)

    def __bool__(self):
        return len(self) > 0
    __nonzero__ = __bool__ # 2

    def send(self, **kwargs):
        if not self: return None
        self.kwargs.update(kwargs)
        return super(Email, self).send()


class EmailItem(object):
    def __init__(self, item):
        self.item = item

    def __unicode__(self):
        item = self.item
        new_item = self.item.newest
        old_item = self.item.last
        citem = self.item.cheapest

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

        title = new_item.body["title"]
        if item.is_digital():
            title += " (digital)"

        if item.is_cheapest():
            lines.append(
                "    <h3><a style=\"color:green\" href=\"{}\">{}</a></h3>".format(
                    url,
                    title
                )
            )

        elif item.is_richest():
            lines.append(
                "    <h3><a style=\"color:red\" href=\"{}\">{}</a></h3>".format(
                    url,
                    title
                )
            )

        else:
            lines.append(
                "    <h3><a href=\"{}\">{}</a></h3>".format(
                    url,
                    title
                )
            )

        lines.append("    <p>")
        lines.append("        <b>${:.2f}</b>".format(new_item.body["price"]))
        if old_item:
            lines.append("        was <b>${:.2f}</b></p>".format(
                old_item.body["price"],
            ))
        lines.append("    </p>")

        if citem:
            lines.append("    <p>Lowest price was <b>${:.2f}</b> on {} ({} times total)</p>".format(
                citem.body.get("price", 0.0),
                citem._created.strftime("%B %d, %Y"),
                citem.price_count,
            ))

        lines.append("    <p>")
        page_url = new_item.body.get("page_url", "")
        added = new_item.body.get("added", "unknown")
        if page_url:
            lines.append("        <a href=\"{}\">added {}</a>".format(page_url, added))

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

    def __str__(self):
        if is_py3:
            return self.__unicode__()
        else:
            return self.__unicode__().encode("UTF-8")


class WatchlistItem(Orm):

    table_name = "watchlist_item"
    connection_name = "watchlist"

    uuid = Field(str, True, max_size=32)
    price = Field(int, True)
    body = ObjectField(True)

    uuid_index = Index("uuid", "price")

    def modify(self, fields, **fields_kwargs):
        fields = self.modify_fields(fields, **fields_kwargs)
        if "body" in fields:
            if "price" in fields:
                fields["body"].setdefault("price", fields["price"])
            if "uuid" in fields:
                fields["body"].setdefault("uuid", fields["uuid"])
        return super(WatchlistItem, self).modify(fields)

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


class Item(object):
    @property
    def uuid(self):
        return self.newest.uuid

    @property
    def email(self):
        return EmailItem(self)

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

    def __init__(self, uuid, body, price, **kwargs):
        self.newest = WatchlistItem(
            uuid=uuid,
            body=body,
            price=price,
            **kwargs
        )

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

