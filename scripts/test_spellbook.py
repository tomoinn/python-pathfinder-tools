from spells import AllSpells, SpellBook, CasterClass
book = SpellBook(AllSpells())
book.add_spells(caster_class=CasterClass.BARD, max_level=0)
book.make_pdf()