# -*- coding: utf-8 -*-
from __future__ import unicode_literals, division, print_function, absolute_import
from unittest import TestCase
import os

import testdata
from captain.client import Captain

from watchlist.models import Item, Email, EmailItem


def setUpModule():
    Item.interface.delete_tables(disable_protection=True)


def tearDownModule():
    Item.interface.delete_tables(disable_protection=True)


def get_item(item=None, **kwargs):
    if item:
        body = dict(item.body)
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

        body = {
            "url": "http://foo.com",
            "image": "http://foo.com/bar.jpg",
        }

        body.update({
            "title": "expensive",
            "price": 100.00,
        })
        it = Item(body=dict(body))
        em.append(it, it)

        body.update({
            "title": "cheaper",
            "price": 10.00,
        })
        it = Item(body=dict(body))
        em.append(it, it)

        body.update({
            "title": "cheapest",
            "price": 1.00,
        })
        it = Item(body=dict(body))
        em.append(it, it)

        html = em.body_html
        self.assertTrue(html.index("cheapest") < html.index("cheaper") < html.index("expensive"))

    def test_subject(self):
        em = Email("foo")
        it = Item(body={"price": 1})
        em.append(Item(body={"price": 1}), Item(body={"price": 2}))
        em.append(Item(body={"price": 2}), Item(body={"price": 1}))

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
        it = Item(body=body)

        em.append(it, it)

        with self.assertRaises(UnicodeEncodeError):
            str(em.body_html)

        #em.send()
        str(em.body_html.encode("utf8"))

    def test_unicode_email_item(self):
        body = {
            "url": "http://foo.com",
            #"title": "foo",
            "title": "\u2713",
            "image": "http://foo.com/bar.jpg",
            "price": 12.34
        }

        it = Item(body=body)
        ei = EmailItem(it, it)
        ei_str = str(ei) # if no error is raised, we pass!
        #pout.v(type(ei_str), ei_str)
        #print ei_str

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

        #pout.v(em)
        #em.send()

    def test_nostock(self):
        nit = get_item(price=0, digital=False)
        oit = get_item(nit, price=100)
        em = Email("wishlist-name")
        em.append(oit, nit)
        self.assertTrue("Out of Stock" in em.body_html)

        nit = get_item(price=0, digital=True)
        oit = get_item(nit, price=100)
        em = Email("wishlist-name")
        em.append(oit, nit)
        self.assertTrue("Lower Priced" in em.body_html)

class EmailItemTest(TestCase):
    def test_digital(self):
        nit = Item.create(
            price=100,
            body={
                "url": testdata.get_url(),
                "title": testdata.get_words(),
                "digital": True,
                "price": 1.0
            },
            uuid="foo"
        )
        oit = Item.create(
            price=200,
            body=nit.body,
            uuid=nit.uuid
        )

        ei = EmailItem(oit, nit)
        self.assertTrue("digital" in "{}".format(ei))


class ItemTest(TestCase):
    def test_cheapest(self):
        it = Item.create(price=10, body={}, uuid="foo")
        it = Item.create(price=1, body={}, uuid="foo")
        it = Item.create(price=1000, body={}, uuid="foo")
        it = Item.create(price=100, body={}, uuid="foo")
        it = Item.create(price=0, body={}, uuid="foo")

        cheapest = Item.cheapest("foo")
        self.assertEqual(1, cheapest.price)

    def test_fset(self):
        uuid = testdata.get_ascii(16)
        body = {
            "uuid": uuid,
            "price": 100.0,
        }
        it = Item(body=body)
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

        it = Item(
            uuid=uuid,
            body={"foo": 1},
            price=17.14
        )
        it.save()

        it2 = Item(
            uuid=uuid,
            body={"foo": 1},
            price=17.15
        )
        it2.save()

        self.assertEqual(it.uuid, it2.uuid)
        self.assertLess(it.pk, it2.pk)

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

