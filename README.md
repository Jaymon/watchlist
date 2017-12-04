# Watchlist

Uses [wishlist](https://github.com/Jaymon/wishlist) to monitor an Amazon wishlist and send an email when prices change.

## Installation

Install:

    $ pip install watchlist

Or be bleeding edge:

    $ pip install "git+https://github.com/Jaymon/watchlist#egg=wishlist"

You'll need to setup a [Sendgrid](https://sendgrid.com/) account (if you don't have one already, there is a free tier).

And you'll need some environment variables:

    export SENDGRID_KEY=YOUR_SENDGRID_API_KEY
    export BROW_CACHE_DIR=/var/watchlist
    export PROM_DSN_1="prom.interface.sqlite.SQLite://${BROWSER_CACHE_DIR}/watchlist.db#watchlist"

Make sure your `BROW_CACHE_DIR` actually exists. 

[wishlist has dependencies also](https://github.com/Jaymon/wishlist).

If you have a private wishlist, then you'll need to login to Amazon before you can run watchlist, you can follow the [wishlist directions](https://github.com/Jaymon/wishlist#1-minute-gettings-started) to signin.

Then you can run this:

    $ watchlist NAME

Where `NAME` is the Wishlist name, basically the string in the url `https://www.amazon.com/gp/registry/wishlist/NAME`. You can set this command up in a cron job to have it run periodically and send you updates.

