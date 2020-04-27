# run with e.g. python test.py | dot -Tpng | display to show the result
from pathfinder import pyfeats

feats = pyfeats.read_feat_csv()

print(feats.graph('|'.join(
    ["deadly aim", "rapid shot", "point-blank shot", "manyshot", "improved precise shot", "sniper's lantern",
     "acute shot", "lob shot", "ranged disarm", "ranged trip", "trick shooter", "exceptional pull", "master sniper",
     "greater snap shot", "focused shot", "circuitous shot", "pinpoint targetting", "clustered shots", "friendly fire",
     "enfilading fire", "ranged disable", "tracer fire"]),
    children=False).to_string())
