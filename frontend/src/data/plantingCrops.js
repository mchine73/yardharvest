// Planting-calendar crop categories and their translated labels.
//
// The category string IS the id. It is PlantingGuide.category as seeded by
// init_planting_guide() in app/api/planting_api.py, what the planting log
// writes to SellerPlanting.category, what harvest-interest subscriptions
// store, and the /planting-guide/<category> URL segment. So it stays English
// everywhere it is SENT; only what the reader SEES goes through cropLabel().
//
// The API accepts any category string, so an unknown one renders as-is.

export const PLANTING_CATEGORIES = [
  'Tomatoes', 'Peppers (Hot)', 'Peppers (Sweet)', 'Cucumbers', 'Squash (Summer)',
  'Squash (Winter)', 'Herbs', 'Leafy Greens', 'Root Vegetables', 'Beans', 'Corn',
  'Berries', 'Melons', 'Peas', 'Onions/Garlic', 'Brassicas', 'Other',
];

const CROP_KEYS = {
  'Tomatoes': 'crops.tomatoes',
  'Peppers (Hot)': 'crops.peppersHot',
  'Peppers (Sweet)': 'crops.peppersSweet',
  'Cucumbers': 'crops.cucumbers',
  'Squash (Summer)': 'crops.squashSummer',
  'Squash (Winter)': 'crops.squashWinter',
  'Herbs': 'crops.herbs',
  'Leafy Greens': 'crops.leafyGreens',
  'Root Vegetables': 'crops.rootVegetables',
  'Beans': 'crops.beans',
  'Corn': 'crops.corn',
  'Berries': 'crops.berries',
  'Melons': 'crops.melons',
  'Peas': 'crops.peas',
  'Onions/Garlic': 'crops.onionsGarlic',
  'Brassicas': 'crops.brassicas',
  'Other': 'crops.other',
};

/** The reader-facing name of a planting category, in the page's language. */
export function cropLabel(t, category) {
  const key = CROP_KEYS[category];
  return key ? t(key, category) : (category || '');
}
