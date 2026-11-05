// Preguntas frecuentes — Spanish edition of faq.js, served at /es/faq and on
// the Spanish home page. FAQ.jsx picks this module when the page is Spanish.
//
// KEEP IN SYNC with faq.js: same ids, categories, order, flags (featured,
// needsPricing), links and {{TOKENS}} — only the human-readable text differs.
// faq.parity.test.js enforces it, and app/seo.py mirrors the questions and
// answers for the FAQPage structured data.
//
// Voice: tú, Spain Spanish (castellano peninsular), as in the rest of the
// catalog. UI labels are quoted exactly as the Spanish screens show them
// ("Crear un huerto", "Finanzas", "Facturación y transferencias").

export const FAQ_TITLE = 'Preguntas frecuentes';
export const FAQ_DESCRIPTION =
  'Respuestas sobre YardHarvest: cuánto cuesta, qué añade Garden Pro, a ' +
  'dónde va el dinero de las cuotas, cómo conseguir una parcela y qué pasa ' +
  'con tus datos.';
export const FAQ_INTRO =
  'Las preguntas que más nos hacen quienes organizan huertos y quienes ' +
  'cultivan en ellos, en pocas palabras. Para instrucciones paso a paso, el ' +
  'centro de ayuda tiene el detalle.';

export const CATEGORIES = [
  { key: 'start', title: 'Primeros pasos', icon: 'bi-flag' },
  { key: 'cost', title: 'Coste y Garden Pro', icon: 'bi-tag' },
  { key: 'money', title: 'Cuotas y pagos', icon: 'bi-cash-stack' },
  { key: 'gardeners', title: 'Para hortelanos', icon: 'bi-flower1' },
  { key: 'data', title: 'Privacidad y tus datos', icon: 'bi-shield-lock' },
];

export const QUESTIONS = [
  // ---------------------------------------------------------------- start --
  {
    id: 'what-is-yardharvest',
    category: 'start',
    featured: true,
    q: '¿Qué es YardHarvest?',
    a: 'Un programa para llevar un huerto comunitario. Quienes lo organizan gestionan en un solo lugar las parcelas y la lista de espera, los integrantes, las cuotas, los eventos, los turnos de voluntariado, los anuncios, las herramientas compartidas y los registros de cosecha. Los hortelanos lo usan para encontrar un huerto, conseguir una parcela, pagar sus cuotas y registrar lo que cultivan.',
    link: { to: '/about', label: 'Nuestra historia' },
  },
  {
    id: 'who-is-it-for',
    category: 'start',
    q: '¿Para quién es?',
    a: 'Para quienes organizan huertos comunitarios y los voluntarios que les ayudan, para los hortelanos que alquilan una parcela y para las organizaciones que llevan varios huertos, como organizaciones sin ánimo de lucro, programas de extensión y departamentos de parques.',
  },
  {
    id: 'start-a-garden',
    category: 'start',
    featured: true,
    q: '¿Cómo creo un huerto en YardHarvest?',
    a: 'Crea una cuenta gratis y luego elige «Crear un huerto». Solo necesitas un nombre y una ubicación; todo lo demás puede esperar. Tu huerto queda publicado de inmediato con su propia página pública, que es el enlace que compartes con tus vecinos.',
    link: { to: '/help/create-a-garden', label: 'Crea tu huerto' },
  },
  {
    id: 'is-the-garden-page-public',
    category: 'start',
    q: '¿La página de mi huerto es pública?',
    a: 'Sí. Muestra la descripción del huerto, la dirección, las normas, las fechas de la temporada, las parcelas disponibles y las fotos que publiques, y los buscadores la indexan, así que también sirve como sitio web del huerto.',
  },

  // ----------------------------------------------------------------- cost --
  {
    id: 'is-it-free',
    category: 'cost',
    featured: true,
    q: '¿YardHarvest es gratis?',
    a: 'Para los hortelanos, siempre. Para quienes organizan, llevar un huerto también es gratis: parcelas e integrantes ilimitados, la lista de espera, los eventos, los anuncios, el muro de la comunidad, el inventario de herramientas, el registro de cosechas, la configuración de las transferencias y el cobro en persona con Tap to Pay. Garden Pro añade encima las herramientas de gestión.',
    link: { to: '/help/free-and-pro', label: 'Qué es gratis y qué añade Pro' },
  },
  {
    id: 'garden-pro',
    category: 'cost',
    q: '¿Cuánto cuesta Garden Pro y qué añade?',
    a: '{{PRO_MONTHLY}} al mes o {{PRO_YEARLY}} al año, con una prueba gratis de {{TRIAL_DAYS}} días que no pide tarjeta. Pro añade las cuotas (generarlas, hacer su seguimiento, recordatorios y exportaciones), los gastos y el resumen financiero, los informes para financiadores, los mensajes directos y masivos, los correos de anuncios, el muro de fotos, los turnos de voluntariado, el préstamo de herramientas con etiquetas QR y el diseñador del plano.',
    aNoPrice: 'Garden Pro es una suscripción mensual o anual con una prueba gratis que no pide tarjeta; los precios actuales están en la página de precios. Pro añade las cuotas (generarlas, hacer su seguimiento, recordatorios y exportaciones), los gastos y el resumen financiero, los informes para financiadores, los mensajes directos y masivos, los correos de anuncios, el muro de fotos, los turnos de voluntariado, el préstamo de herramientas con etiquetas QR y el diseñador del plano.',
    link: { to: '/pricing', label: 'Ver precios' },
  },
  {
    id: 'do-gardeners-pay',
    category: 'cost',
    q: '¿Los hortelanos pagan algo por usar YardHarvest?',
    a: 'No. Los hortelanos nunca pagan nada a YardHarvest. Si tu huerto cobra cuotas por las parcelas, ese dinero es para tu huerto.',
  },
  {
    id: 'contract-and-canceling',
    category: 'cost',
    q: '¿Hay contrato? ¿Qué pasa si cancelamos Pro?',
    a: 'No hay contrato: Pro es mensual o anual y puedes cancelar cuando quieras. Sigue activo hasta el final del periodo que ya has pagado y no se borra nada. Los registros de cuotas, las fotos, los turnos y los informes se conservan, en modo de solo lectura hasta que vuelvas, y todo lo gratuito sigue funcionando igual.',
  },
  {
    id: 'several-gardens',
    category: 'cost',
    q: 'Llevamos varios huertos. ¿Hay un plan para nosotros?',
    a: 'Sí. Las redes de huertos y los programas municipales tienen precios por volumen por huerto, facturación centralizada e informes de impacto de toda la red. Reserva una llamada y preparamos un plan.',
    link: { to: '/book', label: 'Reservar una llamada' },
  },

  // ---------------------------------------------------------------- money --
  {
    id: 'where-does-the-money-go',
    category: 'money',
    featured: true,
    q: '¿A dónde va el dinero de las cuotas?',
    a: 'Directamente a tu huerto. Los pagos llegan a una cuenta de Stripe a nombre de tu huerto, y Stripe los transfiere a tu banco. YardHarvest nunca guarda el dinero de tu huerto.',
    link: { to: '/help/money-overview', label: 'Cómo se mueve el dinero' },
  },
  {
    id: 'platform-fee',
    category: 'money',
    needsPricing: true,
    q: '¿YardHarvest se queda con una parte de lo que cobramos?',
    a: 'No. YardHarvest no se queda con nada de las cuotas, los cobros en persona ni las ventas. Los pagos con tarjeta sí tienen comisiones de procesamiento de Stripe, y la pestaña «Finanzas» muestra, para cada pago, cuánto se cobró, las comisiones y cuánto llegó a tu banco.',
    aFee: 'YardHarvest se queda con el {{DUES_FEE}} % de cada pago que cobra tu huerto. Los pagos con tarjeta también tienen comisiones de procesamiento de Stripe. La pestaña «Finanzas» muestra, para cada pago, cuánto se cobró, las comisiones y cuánto llegó a tu banco.',
  },
  {
    id: 'how-members-pay',
    category: 'money',
    q: '¿Cómo pueden pagar sus cuotas los integrantes?',
    a: 'En línea con tarjeta o transferencia bancaria, desde la página del huerto; en persona con Tap to Pay en iPhone; o en efectivo o con cheque, que quien organiza registra a mano.',
    link: { to: '/help/dues', label: 'Generar y cobrar las cuotas' },
  },
  {
    id: 'collect-online',
    category: 'money',
    q: '¿Qué necesitamos para cobrar cuotas en línea?',
    a: 'Una cuenta para recibir transferencias. Conectas tu huerto a Stripe desde «Facturación y transferencias», sin salir de YardHarvest. Stripe te pregunta quién eres y a dónde enviar el dinero, algo que la ley exige a cualquiera que reciba pagos. Mientras no esté lista, los integrantes no pueden pagar en línea.',
    link: { to: '/help/stripe-setup', label: 'Configura las transferencias con Stripe' },
  },

  // ------------------------------------------------------------ gardeners --
  {
    id: 'get-a-plot',
    category: 'gardeners',
    featured: true,
    q: '¿Cómo encuentro un huerto y consigo una parcela?',
    a: 'Explora los huertos, abre el que te quede cerca y reserva una parcela disponible o apúntate a su lista de espera. Quien organiza aprueba las solicitudes y te avisa en cualquier caso.',
    link: { to: '/gardens', label: 'Ver huertos' },
  },
  {
    id: 'pay-my-dues',
    category: 'gardeners',
    q: '¿Cómo pago mis cuotas?',
    a: 'Si tu huerto cobra cuotas, verás lo que debes en la página del huerto y podrás pagar con tarjeta o transferencia bancaria. Quien organiza también puede cobrarte en persona o registrar un pago en efectivo por ti.',
  },
  {
    id: 'log-my-harvest',
    category: 'gardeners',
    q: '¿Para qué registrar mi cosecha?',
    a: 'La cosecha total de tu huerto es lo que sus organizadores muestran a los financiadores y al ayuntamiento para que el huerto siga adelante. Lleva unos segundos: qué has cosechado y más o menos cuánto pesa.',
  },

  // ----------------------------------------------------------------- data --
  {
    id: 'do-you-sell-my-data',
    category: 'data',
    q: '¿Venden mis datos?',
    a: 'No. No vendemos información personal y solo la compartimos, por contrato, con los servicios que hacen funcionar YardHarvest, como el alojamiento, los pagos y el correo. Tu nombre visible, tu foto de perfil y lo que publiques se pueden ver en la página pública de tu huerto.',
    link: { to: '/privacy', label: 'Política de privacidad' },
  },
  {
    id: 'export-our-data',
    category: 'data',
    q: '¿Podemos exportar los datos de nuestro huerto?',
    a: 'Sí. Exportar la lista de integrantes es gratis. Con Garden Pro también puedes exportar las cuotas, los registros financieros y los informes para financiadores en CSV.',
  },
  {
    id: 'more-help',
    category: 'data',
    q: '¿Dónde consigo más ayuda?',
    a: 'El centro de ayuda explica paso a paso la configuración, el dinero y la solución de problemas. Si prefieres hablarlo, reserva una llamada.',
    link: { to: '/help', label: 'Ir al centro de ayuda' },
  },
];

/** Accent-insensitive, so "credito" finds "crédito". */
function fold(s) {
  return String(s || '').normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase();
}

/** Questions matching every word of `query`, in their usual order. */
export function searchQuestions(query) {
  const terms = fold(query).trim().split(/\s+/).filter(Boolean);
  if (!terms.length) return QUESTIONS;
  return QUESTIONS.filter((item) => {
    const hay = fold(`${item.q} ${item.a} ${item.aFee || ''} ${item.aNoPrice || ''}`);
    return terms.every((term) => hay.includes(term));
  });
}
