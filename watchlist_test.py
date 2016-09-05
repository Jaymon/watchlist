# -*- coding: utf-8 -*-
from __future__ import unicode_literals
from unittest import TestCase

import testdata

from watchlist.models import Item, Email

def setUpModule():
    Item.interface.delete_tables(disable_protection=True)


def tearDownModule():
    Item.interface.delete_tables(disable_protection=True)


class EmailTest(TestCase):
    def test_body(self):
        uuid = testdata.get_ascii(16),
        body = {
            "url": "http://example.com",
            "title": "this is the title",
            "image": "http://example.com/image.jpg",
            "price": 0.0,
        }

        new_body = dict(body)
        new_body["price"] = 1.00
        new_item = Item(
            uuid=uuid,
            body=new_body,
            price=1.00
        )

        old_body = dict(body)
        old_body["price"] = 10.00
        old_item = Item(
            uuid=uuid,
            body=body,
            price=10.00
        )

        em = Email("wishlist-name")
        em.append(old_item, new_item)

        pout.v(em)
        #em.send()


class ItemTest(TestCase):
    def test_crud(self):
        it = Item(
            uuid=testdata.get_ascii(16),
            body={"foo": 1, "bar": 2},
            price=17.14
        )

        self.assertEqual(1714, it.price)
        self.assertEqual({"foo": 1, "bar": 2}, it.body)

        it.save()
        self.assertLess(0, it.pk)

        self.assertEqual(1714, it.price)
        self.assertEqual({"foo": 1, "bar": 2}, it.body)

        it2 = Item.query.get_pk(it.pk)
        self.assertEqual(1714, it2.price)
        self.assertEqual({"foo": 1, "bar": 2}, it2.body)
        self.assertEqual(it.pk, it2.pk)

    def test_price(self):
        it = Item()
        it.price = 12.34
        self.assertEqual(1234, it.price)

        it.price = 1256
        self.assertEqual(1256, it.price)

