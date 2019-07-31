from pyfeats import MartialFlex, read_feat_csv

m = MartialFlex(feats=read_feat_csv(),
                known_feat_names=['combat expertise', 'improved disarm', 'improved dirty trick',
                                  'improved trip', 'improved unarmed strike', 'toughness',
                                  'weapon focus'],
                bab=0, fighter_level=0, monk_level=0, brawler_level=6,
                str_stat=18, con_stat=0, dex_stat=0, wis_stat=0, int_stat=0, cha_stat=0, race='human')

print('\n'.join([feat.text for feat in sorted(m.get_flex_tree(depth=2, include_no_deps=True, include_teamwork=False))]))
