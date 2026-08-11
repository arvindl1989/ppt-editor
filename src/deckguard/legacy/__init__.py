"""Parked products.

Four things grew inside this repo alongside the deck builder: auditing a
deck against brand rules, repairing or rebranding an existing deck,
mining archetypes out of real decks, and planning a whole deck from a
brief in one shot. Each works, each has tests, and none of them is the
product any more.

They are moved rather than deleted -- the tests still run, so nothing
rots silently, and bringing one back is an import change. What they are
NOT is part of the supported surface: no CLI command, no route, and
nothing in `deckguard` proper may import from here.

`rules_engine` and `inventory` deliberately stayed behind. They are the
brand checker, and the brand checker became preflight.
"""
