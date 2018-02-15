# -*- coding: utf-8 -*-
from __future__ import unicode_literals, division, print_function, absolute_import
from unittest import TestCase
import os

import testdata
from captain.client import Captain

from watchlist.models import Item, Email, EmailItem, WatchlistItem


def setUpModule():
    WatchlistItem.interface.delete_tables(disable_protection=True)


def tearDownModule():
    WatchlistItem.interface.delete_tables(disable_protection=True)


def get_item(item=None, **kwargs):
    if item:
        body = dict(item.newest.body)
        body.update(kwargs)
        body.setdefault("uuid", item.uuid)
        kwargs = body

    price = kwargs.pop("price", testdata.get_int(1000))
    uuid = kwargs.pop("uuid", testdata.get_hash())

    kwargs.setdefault("url", testdata.get_url())
    kwargs.setdefault("digital", testdata.get_bool())
    kwargs.setdefault("image", testdata.get_url())
    kwargs.setdefault("title", testdata.get_words())

    if isinstance(price, float):
        kwargs["price"] = price
        price = int(price * 100.0)
    else:
        kwargs["price"] = float(price) * 0.01

    it = Item(
        price=price,
        body=kwargs,
        uuid=uuid
    )
    return it


class EmailTest(TestCase):
    def test_order(self):
        em = Email("foo")

        uuid = testdata.get_ascii(16)
        body = {
            "url": "http://foo.com",
            "image": "http://foo.com/bar.jpg",
        }

        body.update({
            "title": "expensive",
            "price": 100.00,
        })
        it = Item(uuid=uuid, body=dict(body), price=body["price"])
        em.cheaper_items.append(it)

        body.update({
            "title": "cheaper",
            "price": 10.00,
        })
        it = Item(uuid=uuid, body=dict(body), price=body["price"])
        em.cheaper_items.append(it)

        body.update({
            "title": "cheapest",
            "price": 1.00,
        })
        it = Item(uuid=uuid, body=dict(body), price=body["price"])
        em.cheaper_items.append(it)

        html = em.body_html
        self.assertTrue(html.index("cheapest") < html.index("cheaper") < html.index("expensive"))

    def test_subject_total(self):
        em = Email("foo")
        it = Item(uuid=testdata.get_ascii(16), body={}, price=1)

        it = Item(uuid=testdata.get_ascii(16), body={}, price=2)
        it.save()
        em.cheaper_items.append(Item(uuid=it.uuid, body={}, price=1).email)

        it = Item(uuid=testdata.get_ascii(16), body={}, price=1)
        it.save()
        em.cheaper_items.append(Item(uuid=it.uuid, body={}, price=2).email)

        self.assertFalse("total" in em.subject)

        em.kwargs["item_count"] = 2
        self.assertTrue("total" in em.subject)

    def test_email_unicode(self):
        em = Email("foo")
        body = {
            "url": "http://foo.com",
            #"title": "foo",
            "title": "\u2713",
            "image": "http://foo.com/bar.jpg",
            "price": 12.34
        }
        it = Item(uuid=testdata.get_ascii(16), body=body, price=body["price"])

        em.cheaper_items.append(it)

        with self.assertRaises(UnicodeEncodeError):
            str(em.body_html)

        str(em.body_html.encode("utf8"))

    def test_unicode_email_item(self):
        body = {
            "url": "http://foo.com",
            #"title": "foo",
            "title": "\u2713",
            "image": "http://foo.com/bar.jpg",
            "price": 12.34
        }

        it = Item(uuid=testdata.get_ascii(16), body=body, price=body["price"])
        ei = EmailItem(it)
        ei_str = str(ei) # if no error is raised, we pass!
        #pout.v(type(ei_str), ei_str)
        #print ei_str

    def test_body(self):
        uuid = testdata.get_ascii(16)
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
        old_item.save()

        em = Email("wishlist-name")
        em.cheaper_items.append(new_item)

        #pout.v(em)
        #em.send()

    def test_nostock(self):
        nit = get_item(price=0, digital=False)

        em = Email("wishlist-name")
        em.nostock_items.append(nit)
        self.assertTrue("Out of Stock" in em.body_html)

        nit = get_item(price=0, digital=True)
        oit = get_item(nit, price=100)
        oit.save()
        em = Email("wishlist-name")
        em.cheaper_items.append(nit)
        self.assertTrue("Lower Priced" in em.body_html)


class EmailItemTest(TestCase):
    def test_digital(self):
        nit = Item(
            price=100,
            body={
                "url": testdata.get_url(),
                "title": testdata.get_words(),
                "digital": True,
                "price": 1.0
            },
            uuid="foo"
        )

        ei = EmailItem(nit)
        self.assertTrue("digital" in "{}".format(ei))


class ItemTest(TestCase):
    def test_last(self):
        uuid = testdata.get_hash()
        it = WatchlistItem.create(price=10, body={}, uuid=uuid)
        it = WatchlistItem.create(price=1, body={}, uuid=uuid)
        it = WatchlistItem.create(price=1000, body={}, uuid=uuid)
        it = WatchlistItem.create(price=100, body={}, uuid=uuid)

        it = Item(price=0, body={}, uuid=uuid)
        last = it.last
        self.assertEqual(100, last.price)

    def test_cheapest(self):
        uuid = testdata.get_hash()
        it = WatchlistItem.create(price=10, body={}, uuid=uuid)
        it = WatchlistItem.create(price=1, body={}, uuid=uuid)
        it = WatchlistItem.create(price=100, body={}, uuid=uuid)
        it = WatchlistItem.create(price=0, body={}, uuid=uuid)

        it = Item(price=1000, body={}, uuid=uuid)
        cheapest = it.cheapest
        self.assertEqual(1, cheapest.price)

    def test_is_cheapest(self):
        uuid = testdata.get_hash()
        it = WatchlistItem.create(price=100, body={}, uuid=uuid)
        it = WatchlistItem.create(price=10, body={}, uuid=uuid)

        it = Item(price=1, body={}, uuid=uuid)
        self.assertTrue(it.is_cheapest())
        self.assertFalse(it.is_richest())

    def test_is_richest(self):
        uuid = testdata.get_hash()
        it = WatchlistItem.create(price=100, body={}, uuid=uuid)
        it = WatchlistItem.create(price=10, body={}, uuid=uuid)

        it = Item(price=1000, body={}, uuid=uuid)
        self.assertFalse(it.is_cheapest())
        self.assertTrue(it.is_richest())

    def test_is_newest(self):
        uuid = testdata.get_hash()
        it = Item(price=1000, body={}, uuid=uuid)
        self.assertTrue(it.is_newest())

        it.save()
        it = Item(price=100, body={}, uuid=uuid)
        self.assertFalse(it.is_newest())

    def test_richest(self):
        uuid = testdata.get_hash()
        it = WatchlistItem.create(price=10, body={}, uuid=uuid)
        it = WatchlistItem.create(price=1, body={}, uuid=uuid)
        it = WatchlistItem.create(price=1000, body={}, uuid=uuid)
        it = WatchlistItem.create(price=100, body={}, uuid=uuid)

        it = Item(price=0, body={}, uuid=uuid)
        richest = it.richest
        self.assertEqual(1000, richest.price)

    def test_equality(self):
        uuid = testdata.get_hash()
        price = 10
        it = Item(price=price, body={}, uuid=uuid)

        # make sure when there is non of this item in the db it acts as expected
        self.assertFalse(it.is_cheaper())
        self.assertFalse(it.is_richer())
        self.assertTrue(it.is_newest())
        self.assertTrue(it.is_cheapest())
        self.assertTrue(it.is_stocked())
        self.assertTrue(it.is_richest())

        # now make sure it acts as expected when there is another item
        wit = WatchlistItem.create(price=price, body={}, uuid=uuid)
        self.assertFalse(it.is_cheaper())
        self.assertFalse(it.is_richer())
        self.assertFalse(it.is_newest())
        self.assertTrue(it.is_cheapest())
        self.assertTrue(it.is_stocked())
        self.assertTrue(it.is_richest())



class WatchlistItemTest(TestCase):
    def test_fset(self):
        uuid = testdata.get_ascii(16)
        body = {
            "uuid": uuid,
            "price": 100.0,
        }
        it = WatchlistItem(body=body)
        self.assertEqual(10000, it.price)
        self.assertEqual(uuid, it.uuid)

        body = {
            "uuid": testdata.get_ascii(16),
            "price": 200.0,
        }
        it.body = body
        self.assertEqual(10000, it.price)
        self.assertEqual(uuid, it.uuid)
        self.assertNotEqual(uuid, it.body["uuid"])

    def test_multi(self):
        uuid = testdata.get_ascii(16)

        it = WatchlistItem(
            uuid=uuid,
            body={"foo": 1},
            price=17.14
        )
        it.save()

        it2 = WatchlistItem(
            uuid=uuid,
            body={"foo": 1},
            price=17.15
        )
        it2.save()

        self.assertEqual(it.uuid, it2.uuid)
        self.assertLess(it.pk, it2.pk)

    def test_crud(self):
        it = WatchlistItem(
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

        it2 = WatchlistItem.query.get_pk(it.pk)
        self.assertEqual(1714, it2.price)
        self.assertEqual({"foo": 1, "bar": 2}, it2.body)
        self.assertEqual(it.pk, it2.pk)

    def test_price(self):
        it = WatchlistItem()
        it.price = 12.34
        self.assertEqual(1234, it.price)

        it.price = 1256
        self.assertEqual(1256, it.price)


class MainTest(TestCase):
    def test_connect_failure(self):
        """I recently had an issue where the environment variables got screwed up
        so Watchlist failed to connect to the db and I got a huge email with the
        same error over and over, this makes sure that Watchlist will fail once
        if it can't connect to the db
        """
        c = Captain("watchlist")
        c.cmd_prefix = "python -m"

        environ = dict(os.environ)
        environ["PROM_DSN"] = "prom.interface.sqlite.SQLite:///watchlist.db#watchlist"
        c.env = environ
        r = c.run("foobar --dry-run")
        self.assertTrue("unable to open database file" in r)

