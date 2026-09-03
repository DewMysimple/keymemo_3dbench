export interface AtlasRemap {
  x: number;
  y: number;
  width: number;
  height: number;
}

/**
 * Source-faithful UV rectangles extracted from the read-only runtime data table.
 * Values are normalized against the 4096 × 4096 watercolor atlas.
 */
export const watercolorAtlasRemaps: Readonly<Record<string, AtlasRemap>> = {
  background_2: { x: 0.005859375, y: 0.263466796875, width: 0.399697265625, height: 0.1107421875 },
  cow_1: { x: 0.005859375, y: 0.385927734375, width: 0.169599609375, height: 0.091669921875 },
  cow_2: { x: 0.417275390625, y: 0.263466796875, width: 0.2305078125, height: 0.103154296875 },
  cow_3: { x: 0.659501953125, y: 0.263466796875, width: 0.226201171875, height: 0.0992578125 },
  land_back_1: { x: 0.005859375, y: 0.5900390625, width: 0.45978515625, height: 0.087978515625 },
  land_back_2: { x: 0.005859375, y: 0.689736328125, width: 0.452197265625, height: 0.08244140625 },
  land_back_3: { x: 0.187177734375, y: 0.385927734375, width: 0.5110546875, height: 0.090029296875 },
  land_back_4: { x: 0.47736328125, y: 0.5900390625, width: 0.295927734375, height: 0.07916015625 },
  land_back_5: { x: 0.005859375, y: 0.865341796875, width: 0.413232421875, height: 0.065625 },
  land_front_1: { x: 0.469775390625, y: 0.689736328125, width: 0.330380859375, height: 0.079775390625 },
  land_front_2: { x: 0.005859375, y: 0.942685546875, width: 0.4749609375, height: 0.028916015625 },
  land_front_3: { x: 0.403359375, y: 0.005859375, width: 0.435791015625, height: 0.165703125 },
  land_front_4: { x: 0.430810546875, y: 0.865341796875, width: 0.2600390625, height: 0.058857421875 },
  land_front_5: { x: 0.005859375, y: 0.48931640625, width: 0.452197265625, height: 0.08900390625 },
  land_front_6: { x: 0.005859375, y: 0.783896484375, width: 0.220869140625, height: 0.0697265625 },
  land_front_7: { x: 0.469775390625, y: 0.48931640625, width: 0.351298828125, height: 0.0721875 },
  sheep_1: { x: 0.702568359375, y: 0.865341796875, width: 0.1353515625, height: 0.05865234375 },
  sheep_2: { x: 0.403359375, y: 0.18328125, width: 0.196259765625, height: 0.039990234375 },
  sheep_3: { x: 0.709951171875, y: 0.385927734375, width: 0.1796484375, height: 0.07095703125 },
  sheep_4: { x: 0.238447265625, y: 0.783896484375, width: 0.1599609375, height: 0.0680859375 },
  sheep_5: { x: 0.4925390625, y: 0.942685546875, width: 0.105615234375, height: 0.028095703125 },
  sheep_6: { x: 0.609873046875, y: 0.942685546875, width: 0.10294921875, height: 0.026044921875 },
  sheep_7: { x: 0.724541015625, y: 0.942685546875, width: 0.096181640625, height: 0.015791015625 },
  tree_1: { x: 0.10248046875, y: 0.005859375, width: 0.28916015625, height: 0.233994140625 },
  viaduc_1: { x: 0.410126953125, y: 0.783896484375, width: 0.444814453125, height: 0.0664453125 },
  walker_1: { x: 0.005859375, y: 0.005859375, width: 0.08490234375, height: 0.245888671875 },
};

export const watercolorSdfRemaps: Readonly<Record<string, AtlasRemap>> = {
  tree_1: { x: 0.0048828125, y: 0.0048828125, width: 0.3125, height: 0.257080078125 },
  land_front_3: { x: 0.3271484375, y: 0.0048828125, width: 0.3125, height: 0.14990234375 },
  background_2: { x: 0.0048828125, y: 0.271728515625, width: 0.46875, height: 0.13134765625 },
  walker_1: { x: 0.4833984375, y: 0.271728515625, width: 0.06201171875, height: 0.129150390625 },
  land_back_1: { x: 0.0048828125, y: 0.412841796875, width: 0.46875, height: 0.10107421875 },
  land_back_3: { x: 0.0048828125, y: 0.523681640625, width: 0.46875, height: 0.100830078125 },
  land_back_2: { x: 0.3271484375, y: 0.16455078125, width: 0.46875, height: 0.095458984375 },
  cow_2: { x: 0.4833984375, y: 0.523681640625, width: 0.1708984375, height: 0.0927734375 },
  land_back_4: { x: 0.4833984375, y: 0.412841796875, width: 0.3125, height: 0.091064453125 },
  land_front_5: { x: 0.0048828125, y: 0.63427734375, width: 0.3125, height: 0.088134765625 },
  land_front_1: { x: 0.3271484375, y: 0.63427734375, width: 0.29296875, height: 0.086181640625 },
  cow_3: { x: 0.6298828125, y: 0.63427734375, width: 0.146484375, height: 0.08056640625 },
  land_front_7: { x: 0.0048828125, y: 0.732177734375, width: 0.3125, height: 0.079345703125 },
  viaduc_1: { x: 0.3271484375, y: 0.732177734375, width: 0.46875, height: 0.078125 },
  land_back_5: { x: 0.0048828125, y: 0.8212890625, width: 0.46875, height: 0.07763671875 },
  land_front_6: { x: 0.4833984375, y: 0.8212890625, width: 0.1953125, height: 0.073486328125 },
  cow_1: { x: 0.6884765625, y: 0.8212890625, width: 0.114013671875, height: 0.07275390625 },
  sheep_3: { x: 0.6640625, y: 0.523681640625, width: 0.123291015625, height: 0.061767578125 },
  sheep_4: { x: 0.55517578125, y: 0.271728515625, width: 0.116455078125, height: 0.060791015625 },
  land_front_4: { x: 0.6494140625, y: 0.0048828125, width: 0.1953125, height: 0.05908203125 },
  sheep_1: { x: 0.681396484375, y: 0.271728515625, width: 0.095458984375, height: 0.0498046875 },
  sheep_2: { x: 0.55517578125, y: 0.34228515625, width: 0.146484375, height: 0.040771484375 },
  land_front_2: { x: 0.0048828125, y: 0.90869140625, width: 0.302734375, height: 0.031494140625 },
  sheep_5: { x: 0.3173828125, y: 0.90869140625, width: 0.05859375, height: 0.02294921875 },
  sheep_6: { x: 0.3857421875, y: 0.90869140625, width: 0.061767578125, height: 0.022705078125 },
  sheep_7: { x: 0.457275390625, y: 0.90869140625, width: 0.04931640625, height: 0.013671875 },
};

export const watercolorLayerSchedule: Readonly<Record<string, number>> = {
  tree_1: 0,
  cow_1: 1.25,
  cow_2: 2,
  cow_3: 7,
  walker_1: 7.5,
  land_back_1: 8.25,
  land_front_1: 9.25,
  sheep_2: 14,
  land_front_2: 14,
  sheep_1: 14.5,
  land_front_4: 15,
  land_back_2: 15.5,
  land_back_5: 16,
  land_back_3: 20,
  land_front_3: 22,
  land_front_5: 23.5,
  sheep_4: 31.5,
  sheep_6: 32,
  sheep_3: 32.5,
  land_back_4: 33,
  sheep_5: 33.5,
  sheep_7: 34,
  land_front_6: 39,
  land_front_7: 39.5,
  background_2: 40,
  viaduc_1: 40.5,
};
