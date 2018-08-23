import pyfeats

feats = pyfeats.read_feat_csv()

print(feats.graph('acrobatic steps|rapid shot'))