// Spanish for the growing notes the planting guide stores per crop.
//
// The English lives in the database, seeded once by init_planting_guide() in
// app/api/planting_api.py, and the API serves it as-is — it has no idea what
// language the page is in. So the Spanish is kept here, keyed by the same
// category string the page already has, and swapped in at render time.
//
// `from` is the English each entry was translated from. The parity test
// compares it with the seed, so a reworded note fails CI until the Spanish
// is reworded too, instead of quietly showing a translation of the old text.
//
// Temperatures keep the °F the notes are written in (the gardens are in the
// US) with °C beside them; dates and Omaha/Nebraska/zone 5b stay as stated.

export const CROP_NOTES_ES = {
  'Tomatoes': {
    from: {
      notes: 'Start indoors 6-8 weeks before last frost (approx Mar 1). Transplant after all danger of frost. Stake or cage at planting time. Mulch heavily after soil warms.',
      companion_plants: 'Basil, Carrots, Parsley, Marigolds',
      avoid_near: 'Brassicas, Fennel, Corn',
    },
    notes: 'Siembra en interior de 6 a 8 semanas antes de la última helada (aprox. 1 de marzo). Trasplanta cuando ya no haya riesgo de heladas. Pon tutores o jaulas al plantar. Cubre bien el suelo con acolchado cuando se haya calentado.',
    companion_plants: 'Albahaca, zanahorias, perejil, cempasúchil',
    avoid_near: 'Crucíferas, hinojo, maíz',
  },
  'Peppers (Hot)': {
    from: {
      notes: 'Start indoors 10-12 weeks before last frost (approx Feb 15). Peppers need warm soil (65F+). Harden off gradually over 7-10 days.',
      companion_plants: 'Basil, Tomatoes, Carrots, Onions',
      avoid_near: 'Fennel, Brassicas',
    },
    notes: 'Siembra en interior de 10 a 12 semanas antes de la última helada (aprox. 15 de febrero). Los chiles necesitan suelo cálido (65 °F / 18 °C o más). Acostúmbralos al exterior poco a poco durante 7 a 10 días.',
    companion_plants: 'Albahaca, jitomates, zanahorias, cebollas',
    avoid_near: 'Hinojo, crucíferas',
  },
  'Peppers (Sweet)': {
    from: {
      notes: 'Start indoors 10-12 weeks before last frost (approx Feb 15). Needs warm soil. Bell peppers take longer than most sweet varieties.',
      companion_plants: 'Basil, Tomatoes, Carrots, Spinach',
      avoid_near: 'Fennel, Brassicas',
    },
    notes: 'Siembra en interior de 10 a 12 semanas antes de la última helada (aprox. 15 de febrero). Necesitan suelo cálido. Los pimientos morrones tardan más que la mayoría de las variedades dulces.',
    companion_plants: 'Albahaca, jitomates, zanahorias, espinacas',
    avoid_near: 'Hinojo, crucíferas',
  },
  'Cucumbers': {
    from: {
      notes: 'Direct sow after soil reaches 60F. Can start indoors 3-4 weeks before transplanting. Provide trellis for better fruit and space efficiency.',
      companion_plants: 'Beans, Corn, Peas, Radishes, Sunflowers',
      avoid_near: 'Potatoes, Aromatic herbs',
    },
    notes: 'Siembra directa cuando el suelo llegue a 60 °F (16 °C). También puedes sembrarlos en interior de 3 a 4 semanas antes de trasplantar. Ponles un enrejado: dan mejores frutos y ahorras espacio.',
    companion_plants: 'Frijoles, maíz, chícharos, rábanos, girasoles',
    avoid_near: 'Papas, hierbas aromáticas',
  },
  'Squash (Summer)': {
    from: {
      notes: 'Direct sow after last frost when soil is warm. Harvest frequently when small for best flavor. Very productive - 2-3 plants feeds a family.',
      companion_plants: 'Corn, Beans, Nasturtiums, Marigolds',
      avoid_near: 'Potatoes',
    },
    notes: 'Siembra directa después de la última helada, con el suelo cálido. Cosecha seguido y cuando estén pequeñas para un mejor sabor. Muy productiva: 2 o 3 plantas alcanzan para una familia.',
    companion_plants: 'Maíz, frijoles, capuchinas, cempasúchil',
    avoid_near: 'Papas',
  },
  'Squash (Winter)': {
    from: {
      notes: 'Needs long warm season. Direct sow after frost. Cure in sun for 10 days after harvest for storage. Butternut, acorn, and spaghetti squash do well in Omaha.',
      companion_plants: 'Corn, Beans, Nasturtiums',
      avoid_near: 'Potatoes',
    },
    notes: 'Necesita una temporada larga y cálida. Siembra directa después de las heladas. Para guardarla, déjala curar al sol 10 días después de cosecharla. Las calabazas butternut, bellota y espagueti se dan bien en Omaha.',
    companion_plants: 'Maíz, frijoles, capuchinas',
    avoid_near: 'Papas',
  },
  'Herbs': {
    from: {
      notes: 'Many herbs (parsley, cilantro, dill) can be direct sown early. Basil is frost-sensitive - wait until after May 10. Perennial herbs (thyme, oregano, chives) overwinter well in Zone 5b.',
      companion_plants: 'Most vegetables benefit from nearby herbs',
      avoid_near: 'Varies by herb type',
    },
    notes: 'Muchas hierbas (perejil, cilantro, eneldo) se pueden sembrar directo desde temprano. La albahaca no aguanta las heladas: espera hasta después del 10 de mayo. Las hierbas perennes (tomillo, orégano, cebollín) pasan bien el invierno en la zona 5b.',
    companion_plants: 'A la mayoría de las hortalizas les conviene tener hierbas cerca',
    avoid_near: 'Depende del tipo de hierba',
  },
  'Leafy Greens': {
    from: {
      notes: 'Cool-season crop. Spring sowing: late March to late April. Fall sowing: mid-August to mid-September. Lettuce, spinach, kale, Swiss chard. Use shade cloth in summer heat.',
      companion_plants: 'Carrots, Radishes, Strawberries, Chives',
      avoid_near: 'Celery, Parsley (competition)',
    },
    notes: 'Cultivo de temporada fresca. Siembra de primavera: de finales de marzo a finales de abril. Siembra de otoño: de mediados de agosto a mediados de septiembre. Lechuga, espinaca, kale, acelga. Usa malla de sombra con el calor del verano.',
    companion_plants: 'Zanahorias, rábanos, fresas, cebollín',
    avoid_near: 'Apio, perejil (compiten)',
  },
  'Root Vegetables': {
    from: {
      notes: 'Carrots, beets, radishes, turnips. Spring sowing: early April. Fall sowing: late July to early September. Radishes mature in 25-30 days. Carrots need loose, rock-free soil.',
      companion_plants: 'Peas, Beans, Lettuce, Onions',
      avoid_near: 'Dill (attracts carrot fly)',
    },
    notes: 'Zanahorias, betabeles, rábanos, nabos. Siembra de primavera: principios de abril. Siembra de otoño: de finales de julio a principios de septiembre. Los rábanos maduran en 25 a 30 días. Las zanahorias necesitan suelo suelto y sin piedras.',
    companion_plants: 'Chícharos, frijoles, lechuga, cebollas',
    avoid_near: 'Eneldo (atrae a la mosca de la zanahoria)',
  },
  'Beans': {
    from: {
      notes: 'Direct sow after last frost when soil is 60F+. Bush beans produce earlier; pole beans produce longer. Inoculate with rhizobia for best nitrogen fixation.',
      companion_plants: 'Corn, Squash, Carrots, Cucumbers',
      avoid_near: 'Onions, Garlic, Fennel',
    },
    notes: 'Siembra directa después de la última helada, con el suelo a 60 °F (16 °C) o más. Los frijoles de mata producen antes; los de guía producen por más tiempo. Inocúlalos con rizobios para fijar mejor el nitrógeno.',
    companion_plants: 'Maíz, calabaza, zanahorias, pepinos',
    avoid_near: 'Cebollas, ajo, hinojo',
  },
  'Corn': {
    from: {
      notes: 'Direct sow when soil is 60F+. Plant in blocks (at least 4 rows) for good pollination, not single rows. Sweet corn varieties do well in Nebraska.',
      companion_plants: 'Beans, Squash, Peas, Cucumbers',
      avoid_near: 'Tomatoes (corn earworm)',
    },
    notes: 'Siembra directa con el suelo a 60 °F (16 °C) o más. Para que se polinice bien, siembra en bloques (al menos 4 hileras), no en una sola hilera. Las variedades de maíz dulce se dan bien en Nebraska.',
    companion_plants: 'Frijoles, calabaza, chícharos, pepinos',
    avoid_near: 'Jitomates (gusano elotero)',
  },
  'Berries': {
    from: {
      notes: 'Perennials. Plant bare-root stock in early-mid April. Strawberries produce the first year (day-neutral) or second year (June-bearing). Raspberries and blackberries fruit in year 2+.',
      companion_plants: 'Borage, Lettuce, Spinach, Thyme',
      avoid_near: 'Tomatoes, Peppers, Eggplant (disease spread)',
    },
    notes: 'Perennes. Planta a raíz desnuda de principios a mediados de abril. Las fresas producen el primer año (las de día neutro) o el segundo (las de junio). Las frambuesas y zarzamoras dan fruto a partir del año 2.',
    companion_plants: 'Borraja, lechuga, espinaca, tomillo',
    avoid_near: 'Jitomates, chiles y pimientos, berenjena (contagio de enfermedades)',
  },
  'Melons': {
    from: {
      notes: 'Start indoors 4 weeks before transplanting. Needs warm soil (70F+) and long season. Use black plastic mulch to warm soil. Cantaloupe and watermelon both do well.',
      companion_plants: 'Corn, Sunflowers, Nasturtiums',
      avoid_near: 'Potatoes, Cucumbers (disease cross)',
    },
    notes: 'Siembra en interior 4 semanas antes de trasplantar. Necesita suelo cálido (70 °F / 21 °C o más) y una temporada larga. Usa acolchado de plástico negro para calentar el suelo. El melón cantalupo y la sandía se dan bien.',
    companion_plants: 'Maíz, girasoles, capuchinas',
    avoid_near: 'Papas, pepinos (se pasan enfermedades)',
  },
  'Peas': {
    from: {
      notes: 'Cool-season crop - plant as early as soil can be worked (late March). Peas tolerate light frost. Provide trellis. Can also plant fall crop in late August.',
      companion_plants: 'Carrots, Radishes, Turnips, Corn',
      avoid_near: 'Onions, Garlic',
    },
    notes: 'Cultivo de temporada fresca: siembra en cuanto se pueda trabajar el suelo (finales de marzo). Los chícharos aguantan heladas ligeras. Ponles un enrejado. También puedes sembrar una cosecha de otoño a finales de agosto.',
    companion_plants: 'Zanahorias, rábanos, nabos, maíz',
    avoid_near: 'Cebollas, ajo',
  },
  'Onions/Garlic': {
    from: {
      notes: 'Onion sets or transplants go out in early-mid April. Garlic is planted in October for next summer harvest. Choose long-day onion varieties for Nebraska.',
      companion_plants: 'Carrots, Beets, Lettuce, Tomatoes',
      avoid_near: 'Beans, Peas',
    },
    notes: 'Los bulbillos o plántulas de cebolla se plantan de principios a mediados de abril. El ajo se planta en octubre para cosecharlo el verano siguiente. En Nebraska, elige variedades de cebolla de día largo.',
    companion_plants: 'Zanahorias, betabeles, lechuga, jitomates',
    avoid_near: 'Frijoles, chícharos',
  },
  'Brassicas': {
    from: {
      notes: 'Cool-season. Spring: start indoors mid-Feb, transplant late March/April. Fall: start indoors mid-June, transplant late July/Aug. Includes broccoli, cabbage, cauliflower, Brussels sprouts, kale.',
      companion_plants: 'Onions, Garlic, Dill, Celery, Potatoes',
      avoid_near: 'Tomatoes, Peppers, Strawberries',
    },
    notes: 'Temporada fresca. Primavera: siembra en interior a mediados de febrero y trasplanta a finales de marzo o en abril. Otoño: siembra en interior a mediados de junio y trasplanta a finales de julio o en agosto. Incluye brócoli, repollo, coliflor, coles de Bruselas y kale.',
    companion_plants: 'Cebollas, ajo, eneldo, apio, papas',
    avoid_near: 'Jitomates, chiles y pimientos, fresas',
  },
  'Other': {
    from: {
      notes: 'Varies by crop. Check specific variety requirements. Omaha Zone 5b last frost ~April 25, first frost ~October 10.',
      companion_plants: 'Varies',
      avoid_near: 'Varies',
    },
    notes: 'Depende del cultivo. Revisa lo que necesita cada variedad. En Omaha (zona 5b), la última helada cae hacia el 25 de abril y la primera hacia el 10 de octubre.',
    companion_plants: 'Depende del cultivo',
    avoid_near: 'Depende del cultivo',
  },
};

const FIELDS = ['notes', 'companion_plants', 'avoid_near'];

/**
 * A guide's stored prose in the page's language. Spanish only when the
 * stored English is the text the Spanish was translated from — a note edited
 * in the database since keeps showing its own words rather than a
 * translation of something it no longer says.
 */
export function cropProse(lang, guide, field) {
  const value = guide?.[field];
  if (!value || !FIELDS.includes(field) || !String(lang || '').startsWith('es')) return value;
  const entry = CROP_NOTES_ES[guide.category];
  return entry && entry.from[field] === value ? entry[field] : value;
}
