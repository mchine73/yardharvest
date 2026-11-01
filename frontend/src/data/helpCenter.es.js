// El Centro de ayuda de YardHarvest, en español — el contenido de /es/help.
//
// The Spanish edition of helpCenter.js. SAME exports, SAME structure: identical
// slugs, category keys, icons, ordering, `pro` flags and section shapes. Only
// the prose differs. helpCenter.parity.test.js fails if the two drift.
//
// Rules for editing this file:
//   * Price tokens stay exactly as written — {{PRO_MONTHLY}}, {{PRO_YEARLY}},
//     {{TRIAL_DAYS}}. A translated token ({{PRECIO}}) renders literally.
//   * Web UI labels are quoted «así» and must match the Spanish catalog
//     (frontend/src/i18n/locales/es/common.json) word for word.
//   * The iOS app is English-only for now, so its screens and buttons
//     («Payments», «Collect Dues», «New Sale», «Money», «Reviews») are named in
//     English, as the reader will see them. Same for messages the server sends
//     in English.
//   * Vocabulary: huerto (never jardín), parcela, cuotas, integrantes,
//     organizador, depósitos (Stripe payouts to the bank), tú.
//
// KEEP IN SYNC: titles/descriptions here are the Spanish mirror of
// app/seo.py HELP_META.

export const HELP_TITLE = 'Ayuda de YardHarvest';
export const HELP_DESCRIPTION =
  'Cómo llevar un huerto comunitario en YardHarvest: configuración, parcelas, ' +
  'integrantes, cuotas, depósitos de Stripe, Tap to Pay y solución de problemas.';
export const HELP_INTRO =
  'Cómo llevar tu huerto en YardHarvest: la configuración, el cobro y qué ' +
  'hacer cuando algo no se ve bien. Escrito para quien organiza el huerto por ' +
  'las noches, no para una mesa de soporte.';

/** What a price token reads as when live pricing could not be fetched. Chosen
 *  to fit the sentences below: "cuesta una cantidad fija al mes", "una prueba
 *  gratis de varios días". */
export const PRICE_FALLBACKS = {
  PRO_MONTHLY: 'una cantidad fija',
  PRO_YEARLY: 'una cantidad fija',
  TRIAL_DAYS: 'varios',
};

export const CATEGORIES = [
  {
    key: 'start',
    title: 'Primeros pasos',
    icon: 'bi-flag',
    blurb: 'Crea un huerto, agrega parcelas y recibe a tus primeros integrantes.',
  },
  {
    key: 'running',
    title: 'El día a día del huerto',
    icon: 'bi-sun',
    blurb: 'Eventos, turnos, herramientas, fotos y cómo mantener a todos al tanto.',
  },
  {
    key: 'money',
    title: 'Dinero y Stripe',
    icon: 'bi-cash-stack',
    blurb: 'Configuración de depósitos, cuotas, Tap to Pay y a dónde va de verdad el dinero.',
  },
  {
    key: 'plans',
    title: 'Planes y facturación',
    icon: 'bi-star',
    blurb: 'Qué es gratis, qué agrega Garden Pro y cómo funciona la facturación.',
  },
  {
    key: 'gardeners',
    title: 'Para hortelanos',
    icon: 'bi-person',
    blurb: 'Pedir una parcela, pagar las cuotas y registrar lo que cosechaste.',
  },
  {
    key: 'trouble',
    title: 'Cuando algo sale mal',
    icon: 'bi-life-preserver',
    blurb: 'Los problemas con los que la gente de verdad se topa, y cómo resolverlos.',
  },
];

export const ARTICLES = [
  // ---------------------------------------------------------------- start ---
  {
    slug: 'create-a-garden',
    category: 'start',
    title: 'Crea tu huerto',
    tagline: 'Los cinco minutos que deciden cómo se ve todo lo demás.',
    description:
      'Cómo crear un huerto comunitario en YardHarvest: los datos que importan, '
      + 'lo que ven los integrantes y lo que puedes cambiar después.',
    keywords: 'crear nuevo huerto configurar empezar alta registro registrarse',
    sections: [
      {
        h: 'Crea el huerto',
        p: [
          'Regístrate y luego ve a «Crear un huerto». Necesitas un nombre y una ubicación; todo lo demás puede esperar. El huerto queda publicado de inmediato con su propia página pública, que es el enlace que vas a compartir con tus vecinos.',
        ],
        steps: [
          'Crea una cuenta y elige el perfil «Encargado del huerto».',
          'Abre «Crear un huerto» desde el menú principal.',
          'Escribe el nombre, la dirección y una descripción corta.',
          'Guarda. Llegas al portal de administración del huerto nuevo.',
        ],
      },
      {
        h: 'Lo que ven los integrantes',
        p: [
          'Tu página pública muestra la descripción, la dirección, las reglas, las fechas de la temporada, las parcelas disponibles y las fotos que hayas publicado. Los buscadores la indexan, así que también funciona como el sitio web del huerto. Escribe la descripción para alguien que te encontró en un mapa, no para la gente que ya te conoce.',
          'La dirección se usa para el marcador del mapa y para los avisos del clima. Si tu huerto está detrás de un edificio o no tiene número, pon la dirección útil más cercana y explica en la descripción cómo llegar.',
        ],
      },
      {
        h: 'Pon las reglas desde el principio',
        p: [
          'Las reglas se escriben en «Ajustes» y aparecen en la página pública. Escríbelas antes de que alguien pida la primera parcela. Cuando alguien ya tiene su parcela, una regla nueva se siente como una regla dirigida a esa persona.',
        ],
        tip: 'Todo esto se puede editar después: el nombre, la descripción, las reglas, las fechas de la temporada, la cantidad de parcelas y el plano. Nada de lo que elijas hoy te amarra.',
      },
    ],
  },
  {
    slug: 'plots-and-layout',
    category: 'start',
    title: 'Las parcelas y el diseñador del huerto',
    tagline: 'Parcelas en un plano, y quién está en cada una.',
    description:
      'Agrega las parcelas del huerto, asígnalas a los integrantes y dibuja el '
      + 'plano del huerto en una cuadrícula para que cada quien vea cuál es la suya.',
    keywords: 'parcelas camas plano cuadrícula asignar reservar reservación diseñador diseño',
    sections: [
      {
        h: 'Agrega tus parcelas',
        p: [
          'Ve a la pestaña «Parcelas» y agrega las parcelas. Cada una necesita un número o un nombre; el tamaño y las notas son opcionales, pero ayudan a la gente a elegir. Las parcelas empiezan como disponibles, y cada parcela disponible aparece en la página pública para que alguien la pida.',
        ],
        steps: [
          'Portal de administración, pestaña «Parcelas».',
          'Agrega cada parcela, o agrégalas en lote si su numeración es sencilla.',
          'Marca como no disponible cualquier parcela que te estés guardando, para que nadie la pida.',
        ],
      },
      {
        h: 'Cómo se pide una parcela',
        p: [
          'Un integrante reserva una parcela desde la página pública. Eso no se la asigna: crea una solicitud que tú revisas. Las reservaciones que esperan tu respuesta aparecen en la pestaña «Parcelas» y, en la app de iOS, en el recuadro «Reviews» de tu panel.',
          'Si la apruebas, la parcela es suya. Si la rechazas, vuelve a estar disponible; en los dos casos le avisamos al integrante.',
        ],
      },
      {
        h: 'La lista de espera',
        p: [
          'Cuando no hay nada disponible, la gente se anota en la lista de espera. Aprobar a alguien de la lista de espera lo saca de ella y le permite pedir una parcela. La lista de espera es el número que vale la pena vigilar: es la medida honesta de la demanda, y es lo que te va a pedir un financiador o el departamento de parques de la ciudad.',
        ],
      },
      {
        h: 'El diseñador del huerto',
        p: [
          'El «Diseñador del huerto» dibuja tu huerto en una cuadrícula para que cada integrante vea dónde está su parcela en el terreno, junto con los caminos, las bodegas, el agua y la composta. Editas un borrador y lo publicas cuando se vea bien, así que los integrantes nunca ven un plano a medio hacer.',
        ],
        pro: true,
      },
    ],
  },
  {
    slug: 'members-and-roles',
    category: 'start',
    title: 'Integrantes y funciones',
    tagline: 'Quién está en tu huerto y qué permite de verdad cada función.',
    description:
      'Aprueba integrantes, exporta tu lista y entiende exactamente qué '
      + 'permisos da cada función del huerto en YardHarvest.',
    keywords: 'integrantes lista funciones roles organizador tesorero permisos quitar exportar csv',
    sections: [
      {
        h: 'Tu lista de integrantes',
        p: [
          'La pestaña «Integrantes» muestra a todas las personas del huerto, con su parcela y su función. Puedes exportar la lista como CSV: sirve para una lista de correo, un formulario del seguro o una solicitud de subvención.',
        ],
      },
      {
        h: 'Qué puede hacer cada función',
        p: [
          'Las funciones dan acceso real al portal de administración. Alguien a quien nombres tesorero puede entrar y llevar las cuentas sin ti; un encargado de voluntariado puede organizar los turnos sin poder ver el dinero.',
        ],
        list: [
          'Organizador: el propietario. Control total, incluidas las funciones, la facturación y la configuración de depósitos. Uno por huerto.',
          'Co-organizador: lleva el huerto (parcelas, integrantes, eventos, turnos, recursos, cuotas y reportes).',
          'Tesorero: cuotas, gastos y reportes. Sin acceso a parcelas, integrantes ni ajustes.',
          'Encargado de voluntariado: eventos y turnos de voluntariado. Sin acceso al dinero ni a los integrantes.',
          'Integrante: sin acceso de administración.',
        ],
      },
      {
        h: 'Dos cosas que solo puede hacer el propietario',
        p: [
          'Cambiar funciones, y todo lo que tenga que ver con la facturación o los depósitos. Las dos se quedan con el organizador, sin importar a quién más nombres.',
          'Es a propósito. Quien puede cambiar funciones puede otorgar cualquier otro permiso, y quien controla la configuración de depósitos decide a qué cuenta bancaria llega el dinero. Un co-organizador puede cobrar y gastar; no puede desviar el dinero.',
        ],
        tip: 'Entregar el huerto por completo (por ejemplo, cuando quien lo fundó se retira) es una transferencia de propiedad, no un cambio de función. Escríbenos y nosotros la hacemos.',
      },
      {
        h: 'Quitar a alguien',
        p: [
          'Quitar a un integrante libera su parcela, que vuelve a estar disponible, y lo saca de la lista. No borra su cuenta, su registro de cosecha ni nada de lo que haya publicado. Si debía cuotas, el registro de esas cuotas se queda para que tus cuentas sigan cuadrando.',
        ],
      },
    ],
  },

  // -------------------------------------------------------------- running ---
  {
    slug: 'events-and-shifts',
    category: 'running',
    title: 'Eventos y turnos de voluntariado',
    tagline: 'Jornadas de trabajo a las que la gente sí llega.',
    description:
      'Crea eventos del huerto con confirmación de asistencia y organiza turnos '
      + 'de voluntariado con inscripciones, recordatorios y registro de asistencia.',
    keywords: 'eventos jornada trabajo asistencia confirmar rsvp voluntariado voluntarios turnos recordatorios calendario',
    sections: [
      {
        h: 'Eventos',
        p: [
          'Los eventos sirven para jornadas de trabajo, comidas compartidas, ventas de plantas y reuniones. Los integrantes confirman su asistencia desde la página del huerto o la app, y tú ves quién dijo que sí. Los eventos se pueden repetir, así que una jornada fija de los sábados es una sola entrada y no veinte.',
          'Cada evento aparece en tu página pública, así que también sirve para darte a conocer: un vecino que nunca te ha visto puede encontrar tu próxima jornada de trabajo.',
        ],
      },
      {
        h: 'Turnos de voluntariado',
        p: [
          'Los turnos son para el trabajo que necesita a ciertas personas a cierta hora: las semanas de riego, voltear la composta, abrir el portón el sábado. Los integrantes se anotan en un horario, tú pones cuántas personas hacen falta y puedes mandar un recordatorio antes de que llegue el día.',
          'Después marcas quién asistió de verdad. Con eso se arma el registro de horas de voluntariado que usan los reportes para financiadores, así que vale la pena dedicarle esos treinta segundos: es la diferencia entre «creemos que nos ayudan unas cuarenta personas» y un número que puedes poner en una solicitud de subvención.',
        ],
        pro: true,
      },
    ],
  },
  {
    slug: 'resources-and-tools',
    category: 'running',
    title: 'Herramientas y recursos compartidos',
    tagline: 'A dónde fue a parar la pala buena.',
    description:
      'Lleva el control de las herramientas compartidas del huerto, imprime '
      + 'etiquetas QR y registra préstamos y devoluciones para saber quién tiene qué.',
    keywords: 'herramientas recursos préstamo prestar qr etiqueta devolver mantenimiento impresora inventario',
    sections: [
      {
        h: 'Arma el inventario',
        p: [
          'Agrega cada artículo compartido que valga la pena controlar: herramientas, carretillas, mangueras, la cortadora de pasto. Tener el inventario es gratis, y aun sin préstamos responde a «¿qué tenemos?», que es casi todo lo que buscas la primera vez que cuentas lo que hay.',
        ],
      },
      {
        h: 'Préstamos',
        p: [
          'Los préstamos te dicen dónde está cada herramienta. Un integrante escanea el código QR del artículo, o tú se lo prestas desde el portal de administración con «Prestar a un integrante». Cada préstamo tiene fecha de devolución, y puedes extenderla o forzar la devolución si alguien deja de dar señales.',
          'Puedes imprimir etiquetas QR directo desde la app de iOS en una impresora de etiquetas Bluetooth, que es la forma más rápida de etiquetar toda la bodega en una tarde.',
        ],
        pro: true,
      },
      {
        h: 'Mantenimiento',
        p: [
          'Usa «Dar de baja» mientras un artículo esté descompuesto: queda «Fuera de servicio» y ya no se puede pedir prestado, en lugar de que alguien camine hasta la bodega para encontrar una cortadora que no arranca desde junio.',
        ],
        pro: true,
      },
    ],
  },
  {
    slug: 'communication',
    category: 'running',
    title: 'Anuncios, mensajes y el muro de la comunidad',
    tagline: 'Tres canales, tres trabajos distintos.',
    description:
      'Cuándo usar anuncios, mensajes directos, el muro de la comunidad y los '
      + 'correos de anuncios para llegar a los integrantes de tu huerto.',
    keywords: 'anuncios mensajes correo email muro comunidad moderación difusión avisar notificar',
    sections: [
      {
        h: 'Anuncios: de uno para todos',
        p: [
          'Los anuncios son el tablero del huerto: el martes no hay agua, cambió el código del portón, la venta de plantas es el sábado. Aparecen en la página del huerto y en la app, y puedes fijar los importantes. Son gratis en todos los huertos.',
        ],
      },
      {
        h: 'Mensajes: de uno a uno',
        p: [
          'Los mensajes directos son para conversar con un solo integrante: un recordatorio de cuotas, una pregunta sobre una parcela descuidada, una bienvenida a alguien nuevo. También puedes escribirle a todo el huerto con «Enviar a todos» cuando algo tiene que llegar a la bandeja de entrada y no a un tablero.',
        ],
        pro: true,
      },
      {
        h: 'El muro de la comunidad: de todos para todos',
        p: [
          'El muro es el espacio de los integrantes: intercambio de plántulas, preguntas, fotos del primer tomate. Los comentarios públicos pasan por un filtro automático de spam y abuso antes de aparecer, y lo dudoso espera a que tú lo apruebes o lo quites.',
        ],
      },
      {
        h: 'Correos de anuncios',
        p: [
          'Los correos de anuncios mandan una nota con formato a la bandeja de entrada de tus integrantes, con el nombre de tu huerto y su dirección de respuesta. Configura los datos del remitente una sola vez en la pestaña «Correos de anuncios», dentro de la sección «Configuración», y revisa la vista previa antes de enviar: el correo es el único canal que no puedes editar después.',
        ],
        pro: true,
      },
    ],
  },
  {
    slug: 'photos-and-impact',
    category: 'running',
    title: 'Fotos, registro de cosecha e impacto',
    tagline: 'La prueba de que la temporada sí pasó.',
    description:
      'Publica fotos del huerto, registra el peso de la cosecha y convierte los '
      + 'datos de una temporada en un reporte de impacto listo para financiadores.',
    keywords: 'fotos galería muro cosecha registro libras impacto reporte financiadores subvención peso',
    sections: [
      {
        h: 'El muro de fotos',
        p: [
          'Las fotos son lo que hace que la página de un huerto se sienta viva para alguien que nunca lo ha visitado. Los integrantes pueden publicar en la galería, y las fotos aparecen en la página pública y en el panel de la app.',
        ],
        pro: true,
      },
      {
        h: 'Registro de cosecha',
        p: [
          'Los integrantes registran lo que cosecharon y cuánto pesó. En la app toma unos segundos, y se va sumando hasta formar el número más útil que tiene un huerto comunitario: las libras de comida cultivadas esta temporada.',
          'Lo difícil es el hábito. Registrar en el huerto, en el momento de cosechar, funciona. Pedirle a la gente que se acuerde en la noche, no.',
        ],
      },
      {
        h: 'Reportes para financiadores',
        p: [
          '«Reportes para financiadores» junta el peso de tu cosecha, las horas de voluntariado, la cantidad de integrantes y la ocupación de las parcelas de un periodo en un documento escrito en el lenguaje que usan quienes otorgan subvenciones. Puedes cambiar los valores de referencia si tu financiador prefiere los suyos, imprimirlo o exportar los números de base.',
          'Esta es la pestaña que se paga sola. Los números ya están en el sistema; el reporte solo te ahorra reconstruirlos en una hoja de cálculo la noche antes de la fecha límite.',
        ],
        pro: true,
      },
    ],
  },

  // ---------------------------------------------------------------- money ---
  {
    slug: 'money-overview',
    category: 'money',
    title: 'Cómo se mueve el dinero en YardHarvest',
    tagline: 'Lee esto antes de configurar nada.',
    description:
      'A dónde van de verdad las cuotas y las ventas del huerto, quién tiene el '
      + 'dinero y por qué YardHarvest nunca se queda en medio entre tú y tus fondos.',
    keywords: 'dinero flujo stripe connect cargo cuotas depósito depósitos comisión plataforma',
    sections: [
      {
        h: 'Tu dinero es tuyo',
        p: [
          'YardHarvest no guarda el dinero de tu huerto. Cuando un integrante paga sus cuotas, o tú cobras con tarjeta en la entrada, el pago va a una cuenta de Stripe a nombre de tu huerto y Stripe lo deposita en tu banco. No somos un intermediario con saldo.',
          'Por eso configurar los depósitos es un paso de verdad y no una casilla que se marca. Stripe tiene que saber quién eres antes de poder mandar dinero a tu banco, y eso es un requisito legal, no de YardHarvest.',
        ],
      },
      {
        h: 'Las tres formas en que entra el dinero',
        list: [
          'Cuotas en línea: un integrante paga desde la página del huerto o la app, con tarjeta o transferencia bancaria.',
          'Cuotas en persona: cobras en la entrada con Tap to Pay en un iPhone, a cuenta del registro de cuotas de un integrante.',
          'Ventas sueltas: plántulas, pases de un día, lo que sea. Tap to Pay por cualquier monto, con una nota.',
        ],
        p: [
          'Las tres llegan al mismo lugar y aparecen en el mismo historial de actividad de «Finanzas». El efectivo y los cheques los registras a mano en el registro de cuotas, y esos nunca pasan por Stripe.',
        ],
      },
      {
        h: 'Cuánto cuesta cobrar un pago',
        p: [
          'Stripe cobra una comisión de procesamiento en cada pago con tarjeta, y en tu huerto esa comisión se cobra a tu cuenta de Stripe. Un pago de cuotas de $50 no llega como $50: llega como unos $48. Eso es Stripe, la misma comisión que paga cualquier negocio por aceptar tarjeta.',
          'YardHarvest no se queda con nada de tus cuotas. No hay comisión de la plataforma en lo que cobra el huerto, así que la única diferencia entre lo que paga un integrante y lo que llega a tu banco es Stripe.',
          'Tu pantalla de «Finanzas» muestra los tres números: lo que se cobró, lo que se llevó Stripe y lo que recibiste. Garden Pro se factura aparte, como suscripción, y no tiene nada que ver con esto.',
        ],
        tip: 'Pon las cuotas en el monto que quieres que paguen los integrantes, no en el que quieres recibir. A los integrantes se les cobra exactamente lo que pones; la comisión de procesamiento sale de tu lado.',
      },
    ],
  },
  {
    slug: 'stripe-setup',
    category: 'money',
    title: 'Configura los depósitos con Stripe',
    tagline: 'El único paso de configuración que vale la pena hacer con calma.',
    description:
      'El registro en Stripe Connect paso a paso para un huerto comunitario: '
      + 'qué te pide Stripe, cuánto tarda y cómo saber que funcionó.',
    keywords: 'stripe connect registro alta depósitos pagos cuenta bancaria configurar verificación ein',
    sections: [
      {
        h: 'Antes de empezar',
        p: [
          'Stripe te va a preguntar quién recibe legalmente el dinero. Ten esto a la mano y todo toma unos diez minutos; si lo buscas a medio camino, toma una semana.',
        ],
        list: [
          'El nombre legal de quien recibe el dinero: la organización sin fines de lucro del huerto, un patrocinador fiscal o una persona.',
          'Un número de identificación fiscal (EIN) si te registras como organización, o un SSN si recibes el dinero a título personal.',
          'Una dirección comercial. Muchas veces rechazan un apartado postal (PO box); usa una dirección física.',
          'El número de cuenta y el número de ruta (routing number) de la cuenta donde debe llegar el dinero.',
          'Un número de teléfono que pueda recibir un código de verificación en este momento.',
        ],
        warn: 'Quien complete esto es, legalmente, quien recibe el dinero. Si tu huerto tiene una organización sin fines de lucro o un patrocinador fiscal, regístrate como esa organización, no a tu nombre. Cambiarlo después significa empezar de cero con una cuenta nueva.',
      },
      {
        h: 'Haz el registro',
        steps: [
          'Portal de administración y luego «Facturación y pagos».',
          'Elige «Configurar los pagos». El formulario de Stripe se abre dentro de YardHarvest.',
          'Responde las preguntas. Puedes guardar sobre la marcha: te deja volver después.',
          'Agrega la cuenta bancaria al final y confirma la verificación por teléfono.',
          'Vuelve a «Facturación y pagos». Tu cuenta debería aparecer como «Conectado».',
        ],
      },
      {
        h: 'Cómo saber que de verdad funcionó',
        p: [
          'Tienen que cumplirse dos cosas, y son independientes. Con los cobros activados puedes recibir dinero. Con los depósitos activados, Stripe puede mandarlo a tu banco. Es totalmente posible tener lo primero sin lo segundo: cobras un pago sin problema y luego el dinero se queda en Stripe esperando un documento.',
          'Tu pestaña «Finanzas» te dice las dos cosas, en palabras sencillas, en la subpestaña «Stripe». Si dice que los pagos y los depósitos están activos, ya terminaste.',
        ],
      },
      {
        h: 'El primer depósito tarda más',
        p: [
          'Stripe suele retener varios días el primer depósito de una cuenta nueva antes de liberarlo, y después se ajusta a un calendario regular. Es una medida normal contra el fraude, no un problema con tu configuración. No cobres las cuotas de toda una temporada el día antes de necesitar el dinero.',
        ],
      },
    ],
  },
  {
    slug: 'dues',
    category: 'money',
    title: 'Generar y cobrar las cuotas',
    tagline: 'De «todos deben $50» a una lista al corriente.',
    description:
      'Genera las cuotas de la temporada para quienes tienen parcela, cobra en '
      + 'línea o en persona, registra el efectivo y da seguimiento a lo pendiente.',
    keywords: 'cuotas pagos temporada generar cobrar perdonar cortesía pendientes recordar efectivo cheque',
    sections: [
      {
        h: 'Genera la temporada',
        p: [
          '«Finanzas», luego la subpestaña «Cuotas» y luego «Generar cuotas». Escribe el monto y se crea un registro por cada persona que tenga parcela en esa temporada. A quien pida una parcela después hay que agregarle su registro, así que genera las cuotas cuando la lista ya esté estable.',
        ],
        pro: true,
      },
      {
        h: 'Lo que de verdad recibe el huerto',
        p: [
          'A los integrantes se les cobra exactamente el monto que pones. Lo que llega a tu banco es un poco menos, porque Stripe toma su comisión de procesamiento de tu lado de la transacción: con tarjeta, alrededor del 3 %. Pon las cuotas en $50 y espera unos $48.',
          'El efectivo y los cheques no tienen ninguna comisión, algo que vale la pena recordar si a tu huerto le funciona cualquiera de los dos. La transferencia bancaria también suele salir más barata que la tarjeta.',
        ],
        tip: 'No pongas las cuotas en $52 para cubrir la comisión. Los integrantes ven el número que pones, y un monto raro trae preguntas que vas a pasar toda la temporada contestando.',
      },
      {
        h: 'Cómo pagan los integrantes',
        p: [
          'Un integrante con cuotas pendientes las ve en la página del huerto y en la app, y puede pagar con tarjeta o transferencia bancaria. El registro se marca como pagado solo; no tienes que conciliar nada.',
          'Si tu cuenta de depósitos no está lista, el pago se rechaza con un mensaje claro. Es a propósito: así no se cobran cuotas a una cuenta que no puede depositártelas.',
        ],
      },
      {
        h: 'Efectivo, cheques y cuotas perdonadas',
        list: [
          'Efectivo o cheque: registra el pago a mano en la fila de cuotas del integrante, con una nota. Nunca pasa por Stripe.',
          '«Perdonado»: cuotas perdonadas por esta temporada. Úsalo en casos de necesidad; se puede deshacer.',
          '«De cortesía»: no se debe ninguna cuota. Úsalo para una parcela que le diste a una escuela o a una organización aliada.',
        ],
      },
      {
        h: 'Dar seguimiento a lo pendiente',
        p: [
          'La subpestaña «Cuotas» muestra quién ya pagó y quién no, y puedes mandar un recordatorio desde la misma fila. La subpestaña «Resumen» te da la «Tasa de cobro», que es el número que hay que vigilar a media temporada: insistir cuando llevas un 60 % cobrado es una conversación; insistir en noviembre es un problema.',
        ],
        pro: true,
      },
    ],
  },
  {
    slug: 'tap-to-pay',
    category: 'money',
    title: 'Tap to Pay en la entrada',
    tagline: 'Cobra con tarjeta en tu iPhone, sin lector.',
    description:
      'Usa Tap to Pay en iPhone desde la app de YardHarvest para cobrar cuotas '
      + 'y hacer ventas de plantas en persona, sin lector de tarjetas.',
    keywords: 'tap to pay iphone terminal tarjeta presencial en persona venta lector nfc cobrar',
    sections: [
      {
        h: 'Lo que necesitas',
        list: [
          'Un iPhone XS o más reciente con iOS 17 o posterior. Los iPad no pueden usar Tap to Pay.',
          'La app de YardHarvest, con sesión iniciada como organizador del huerto. La app todavía está en inglés, así que aquí nombramos sus pantallas tal como aparecen en ella.',
          'La configuración de depósitos terminada, incluidos los pagos con tarjeta en persona activos en tu cuenta de Stripe.',
        ],
        p: [
          'Si tu dispositivo no puede hacerlo, la pantalla «Payments» te lo dice, en lugar de fallar justo cuando acercas una tarjeta.',
        ],
      },
      {
        h: 'Cobrar cuotas en persona',
        steps: [
          'Abre la app, entra a tu huerto y luego a «Payments».',
          'Elige «Collect Dues» y escoge al integrante.',
          'Acerca su tarjeta o su teléfono a la parte de atrás del tuyo.',
          'El registro de cuotas se marca como pagado solo.',
        ],
      },
      {
        h: 'Vender cualquier otra cosa',
        p: [
          '«New Sale» cobra cualquier monto con una nota: plántulas, una bolsa de composta, un pase de un día en una jornada de puertas abiertas. No está ligado a un registro de cuotas. Escribe una nota cada vez: es lo único que te va a decir después para qué eran los $12 del día catorce.',
        ],
      },
      {
        h: 'Si se cae la red a mitad del cobro',
        p: [
          'El pago sí cuenta. Stripe le avisa directamente a YardHarvest lo que pasó, así que el registro de cuotas se liquida aunque tu teléfono se haya quedado sin señal justo después de acercar la tarjeta. No tienes que volver a cobrar: revisa el historial de actividad de «Finanzas» antes de cobrarle dos veces a alguien.',
        ],
      },
    ],
  },
  {
    slug: 'money-feed',
    category: 'money',
    title: 'Cómo leer tu actividad de Stripe',
    tagline: 'Lo que entró, lo que volvió a salir y cuándo llegó al banco.',
    description:
      'Entiende la subpestaña Stripe de Finanzas: el dinero cobrado con tarjeta, '
      + 'las comisiones de la plataforma y de Stripe, los reembolsos, los '
      + 'contracargos y los depósitos al banco.',
    keywords: 'finanzas actividad historial stripe comisiones neto depósitos reembolso disputa contracargo',
    sections: [
      {
        h: 'Dónde encontrarla',
        p: [
          'En la web: «Finanzas» y luego la subpestaña «Stripe». En la app de iOS: «Payments» y luego «Money». Las dos muestran lo mismo, directo de Stripe, y ninguna requiere Garden Pro: es un registro del dinero que ya cobraste.',
        ],
      },
      {
        h: 'Qué significan los totales',
        list: [
          '«Cobrado por Stripe»: todo lo que se les cobró a los integrantes en el periodo, antes de cualquier descuento.',
          '«Comisiones de Stripe»: el procesamiento de tarjeta, que cobra Stripe y sale de tu lado.',
          '«Neto recibido»: lo que de verdad te llegó. Se lee de Stripe en lugar de calcularse, así que toma en cuenta cualquier cosa inusual de un pago.',
          '«Depositado en el banco»: el dinero que Stripe ya te mandó.',
        ],
        p: [
          'Los reembolsos, los contracargos y la comisión de la plataforma tienen cada uno su propia cifra, pero solo cuando hay algo que mostrar. YardHarvest no cobra comisión de la plataforma en lo que cobra el huerto, así que la mayoría de los huertos nunca verán esa línea.',
        ],
      },
      {
        h: 'Los depósitos abarcan toda tu cuenta de Stripe',
        p: [
          'Un depósito no es por huerto. Si llevas dos huertos con una misma cuenta de Stripe, un solo depósito cubre los dos; por eso los depósitos aparecen en el historial pero nunca se suman a los totales de un huerto. Si intentas cuadrar lo cobrado por un huerto contra un depósito, no va a cuadrar, y es normal.',
        ],
      },
      {
        h: 'Reembolsos y contracargos',
        p: [
          'Si reembolsas un pago de cuotas desde tu panel de Stripe, el integrante vuelve a aparecer sin pagar en tu lista automáticamente, así que la lista nunca dice que alguien pagó cuando se le devolvió el dinero.',
          'Un contracargo es cuando el titular de la tarjeta disputa un pago con su banco. Stripe retira el dinero de inmediato y te da un plazo corto para responder con pruebas. Te avisamos cuando se abre uno, y ese aviso es urgente como casi ningún otro en YardHarvest.',
        ],
      },
    ],
  },
  {
    slug: 'stripe-pitfalls',
    category: 'money',
    title: 'Problemas con Stripe que conviene conocer',
    tagline: 'Lo que sale mal, y lo que de verdad significa.',
    description:
      'Problemas comunes de Stripe en huertos comunitarios: depósitos sin '
      + 'configurar, pagos en persona inactivos, cuentas restringidas y '
      + 'depósitos que no aparecen.',
    keywords: 'stripe problemas errores depósitos no está lista pagos en persona tarjeta presencial restringida solucionar',
    sections: [
      {
        h: 'Aviso: «Finish payout onboarding before collecting»',
        p: [
          'Tu cuenta de Stripe todavía no está lista para recibir dinero, así que se rechaza el cobro en lugar de mandar el dinero a un lugar desde donde no te puede llegar. Termina el registro en «Facturación y pagos». Si creías que ya habías terminado, seguramente te topaste con la diferencia entre cobros y depósitos que explicamos abajo.',
        ],
      },
      {
        h: 'Cobros activados, pero depósitos desactivados',
        p: [
          'Son dos interruptores distintos. Puedes recibir pagos sin ningún problema y aun así no poder pasar el dinero a tu banco, normalmente porque Stripe quiere un documento de identidad, un número de identificación fiscal o una cuenta bancaria que todavía no le has dado. El dinero sigue entrando a Stripe y ahí se queda.',
          'La subpestaña «Stripe» de «Finanzas» dice qué falta. Nada de lo que ya cobraste está en riesgo; está esperando.',
        ],
      },
      {
        h: 'Tap to Pay dice que los pagos en persona no están activados',
        p: [
          'Si la app muestra «In-person card payments aren\'t enabled», es porque los pagos con tarjeta en persona son una función de Stripe aparte de los pagos en línea normales, y las cuentas creadas antes de que empezaras a usar Tap to Pay nunca la pidieron. YardHarvest la solicita automáticamente la primera vez que lo intentas, y suele activarse en pocos minutos. Si sigue inactiva, normalmente hay un paso pendiente en tu panel de Stripe.',
        ],
      },
      {
        h: 'No se pudo configurar una ubicación de pago',
        p: [
          'Tap to Pay registra tu teléfono como lector de tarjetas en una ubicación de tu cuenta de Stripe, y una ubicación necesita una dirección comercial real. Si ves «Could not set up a payment location», agrega una dirección en tu panel de Stripe y vuelve a intentarlo.',
        ],
      },
      {
        h: 'Tu cuenta fue restringida',
        p: [
          'Stripe pausó la cuenta, normalmente porque venció un plazo de verificación o un documento dejó de estar vigente. Te avisamos en cuanto nos enteramos, para que no lo descubras cuando una tarjeta falle frente a un integrante. Abre tu panel de Stripe y resuelve lo que te pida.',
        ],
      },
      {
        h: 'El modo de prueba y el modo real son mundos distintos',
        p: [
          'Si estuviste haciendo pruebas en un sandbox de Stripe, nada de eso existe en el modo real («live mode»): ni la cuenta, ni los pagos, ni los ajustes. Revisa en qué modo está tu panel de Stripe antes de concluir que algo no se guardó.',
        ],
      },
      {
        h: 'No aparece ningún depósito',
        p: [
          'Los depósitos le llegan a YardHarvest por una conexión de Stripe distinta de la que trae los pagos. Si tus pagos aparecen pero tus depósitos nunca, esa conexión no está configurada de nuestro lado: avísanos en lugar de suponer que Stripe no te ha pagado, y mientras tanto revisa tu panel de Stripe para saber cómo están las cosas de verdad.',
        ],
      },
    ],
  },

  // ---------------------------------------------------------------- plans ---
  {
    slug: 'free-and-pro',
    category: 'plans',
    title: 'Qué es gratis y qué agrega Garden Pro',
    tagline: 'La lista real, no una tabla de marketing.',
    description:
      'Un desglose preciso de qué funciones de YardHarvest son gratis para '
      + 'todos los huertos comunitarios y cuáles requieren Garden Pro.',
    keywords: 'gratis pro precio precios funciones comparación suscribirse qué incluye',
    sections: [
      {
        h: 'Gratis, siempre',
        p: [
          'Llevar un huerto no cuesta nada. Puedes abrir un huerto, llenarlo, organizarlo y recibir dinero sin pagarnos nunca.',
        ],
        list: [
          'Tu huerto, su página pública, y parcelas e integrantes ilimitados.',
          'La lista de espera, las reservaciones de parcelas y las aprobaciones.',
          'Eventos y confirmaciones de asistencia.',
          'Anuncios y el muro de la comunidad, con moderación automática.',
          'Inventario de herramientas y recursos.',
          'Registro de cosecha.',
          'Avisos del clima.',
          'La configuración de depósitos y el cobro en persona con Tap to Pay.',
          'Tu historial de actividad de Stripe: cada pago, reembolso y depósito.',
          'Exportar la lista de integrantes.',
        ],
      },
      {
        h: 'Garden Pro',
        p: [
          'Pro cuesta {{PRO_MONTHLY}} al mes o {{PRO_YEARLY}} al año, con una prueba gratis de {{TRIAL_DAYS}} días que no pide tarjeta.',
        ],
        list: [
          'Cuotas: generarlas, darles seguimiento, recordatorios, cuotas perdonadas y exportación a CSV.',
          'Gastos y el resumen de finanzas.',
          'Reportes para financiadores.',
          'Mensajes directos y mensajes a todo el huerto.',
          'Correos de anuncios a la bandeja de entrada de los integrantes.',
          'El muro de fotos.',
          'Turnos de voluntariado, inscripciones, recordatorios y asistencia.',
          'Préstamo de herramientas, etiquetas QR y control de mantenimiento.',
          'El diseñador del huerto.',
        ],
      },
      {
        h: 'La línea que trazamos',
        p: [
          'Todo lo que registra dinero que ya cobraste sigue siendo gratis, incluido todo el historial de actividad de Stripe. Poner un muro de pago entre un organizador y el registro de lo que cobró su propio huerto no es un trato que estuviéramos dispuestos a hacer. Lo que Pro cobra es el trabajo administrativo alrededor: generar las cuotas, darles seguimiento y reportar el resultado.',
        ],
      },
    ],
  },
  {
    slug: 'trial-and-billing',
    category: 'plans',
    title: 'Prueba, suscripción y cancelación',
    tagline: 'Cómo funciona la facturación de Garden Pro.',
    description:
      'Empieza una prueba de Garden Pro, suscríbete, cambia de plan o cancela, '
      + 'y qué pasa con tus datos en cada caso.',
    keywords: 'prueba suscripción suscribirse cancelar facturación factura cambiar plan reembolso',
    sections: [
      {
        h: 'La prueba',
        p: [
          'La prueba de Garden Pro dura {{TRIAL_DAYS}} días y no pide tarjeta para empezar. Todo se desbloquea de inmediato. Te avisamos antes de que termine.',
        ],
      },
      {
        h: 'Suscribirte',
        p: [
          'En «Facturación y pagos», elige «Suscribirme por mes» o «Suscribirme por año». El plan mensual cuesta {{PRO_MONTHLY}}; el anual cuesta {{PRO_YEARLY}} y sale más barato. Este pago es aparte del cobro de cuotas de tu huerto: va a YardHarvest y no pasa por la cuenta de Stripe de tu huerto.',
        ],
      },
      {
        h: 'Si falla un pago',
        p: [
          'Stripe vuelve a intentarlo automáticamente durante varios días y te mandamos un correo. Las funciones Pro siguen activas durante un periodo de gracia corto en lugar de apagarse en cuanto vence una tarjeta, porque perder tu lista de cuotas a media temporada por una tarjeta vencida sería una forma absurda de tratar a un huerto.',
        ],
      },
      {
        h: 'Cancelar',
        p: [
          'Cancela cuando quieras y Pro sigue activo hasta el final del periodo que ya pagaste. No se borra nada. Tus registros de cuotas, fotos, turnos y reportes se quedan; simplemente dejan de poder editarse hasta que vuelvas, y todo lo gratis sigue funcionando igual que antes.',
        ],
      },
    ],
  },

  // ------------------------------------------------------------ gardeners ---
  {
    slug: 'for-gardeners',
    category: 'gardeners',
    title: 'Para hortelanos',
    tagline: 'Pedir una parcela, pagar y registrar lo que cosechaste.',
    description:
      'Cómo unirte a un huerto comunitario en YardHarvest, pedir una parcela, '
      + 'pagar tus cuotas y registrar tu cosecha.',
    keywords: 'hortelano integrante unirse parcela pedir reservar pagar cuotas cosecha registro app asistencia',
    sections: [
      {
        h: 'Encontrar un huerto y unirte',
        p: [
          'Entra a «Explorar huertos», abre el que te quede cerca y pide una parcela disponible o anótate en la lista de espera. Tu solicitud le llega al organizador para que la apruebe, y te avisamos sea cual sea la respuesta.',
        ],
      },
      {
        h: 'Pagar tus cuotas',
        p: [
          'Si tu huerto cobra cuotas, verás cuánto debes en la página del huerto y en la app, y puedes pagar con tarjeta o transferencia bancaria. Tu organizador también puede cobrarte en persona o registrar un pago en efectivo a tu nombre.',
          'El dinero va a tu huerto, no a YardHarvest.',
        ],
      },
      {
        h: 'Registrar tu cosecha',
        p: [
          'Registra lo que cosechas y más o menos cuánto pesó. Toma unos segundos y se va sumando: la cosecha total de tu huerto es lo que sus organizadores les muestran a los financiadores y a la ciudad para que el huerto siga adelante. Una báscula de cocina junto a la puerta es todo el truco.',
        ],
      },
      {
        h: 'Todo lo demás',
        list: [
          'Confirma tu asistencia a las jornadas de trabajo y los eventos.',
          'Pide prestadas las herramientas compartidas escaneando la etiqueta QR, si tu huerto tiene eso activado.',
          'Publica en el muro de la comunidad y en la galería de fotos.',
          'Mándale un mensaje directo a tu organizador.',
        ],
      },
    ],
  },

  // -------------------------------------------------------------- trouble ---
  {
    slug: 'common-problems',
    category: 'trouble',
    title: 'Problemas comunes',
    tagline: 'Respuestas rápidas a lo que más pasa.',
    description:
      'Solución de problemas en YardHarvest: correos que no llegan, integrantes '
      + 'que no ven funciones, pestañas Pro bloqueadas y cosas que se ven mal.',
    keywords: 'solucionar problema error falla no llega correo no funciona bloqueado ayuda',
    sections: [
      {
        h: 'Un integrante no ve algo que tú sí ves',
        p: [
          'Lo más probable es que sea una función Pro y el huerto esté en el plan gratis, o que el integrante todavía no esté aprobado. Revisa primero la lista: desde el lado del integrante, una reservación sin aprobar se parece mucho a una cuenta que no funciona.',
        ],
      },
      {
        h: 'No llegan los correos',
        p: [
          'Revisa primero la carpeta de spam y luego la dirección en el perfil del integrante. Si una dirección rebotó de forma permanente o alguien la marcó como spam una vez, se bloquea automáticamente para proteger la entrega de todos los demás en tu huerto, y no recibirá nada hasta que se resuelva.',
        ],
      },
      {
        h: 'Las pestañas Pro se apagaron',
        p: [
          'O terminó la prueba, o se canceló la suscripción, o falló un pago y se acabó el periodo de gracia. «Facturación y pagos» te dice cuál fue. No se borró nada: los datos te están esperando.',
        ],
      },
      {
        h: 'Un número se ve mal en la pantalla de Finanzas',
        p: [
          'Fíjate si la cifra está marcada como un máximo: mientras no se confirme la comisión de Stripe de un pago, «Neto recibido» se muestra como un límite superior y no como una cifra exacta, y lo dice («como máximo»). Además, los depósitos abarcan toda tu cuenta de Stripe, no un solo huerto.',
          'Si algo sigue sin cuadrar, tu panel de Stripe es la fuente oficial del dinero, y preferimos enterarnos de una diferencia a que dejes de confiar en la pantalla sin decir nada.',
        ],
      },
      {
        h: '¿Sigues sin resolverlo?',
        p: [
          'Escríbenos. Dinos el nombre del huerto y qué esperabas que pasara: casi siempre nos basta con eso para encontrarlo.',
        ],
      },
    ],
  },
];

/** Article by slug, or null. */
export function findArticle(slug) {
  return ARTICLES.find((a) => a.slug === slug) || null;
}

/** Articles in a category, in file order. */
export function articlesIn(categoryKey) {
  return ARTICLES.filter((a) => a.category === categoryKey);
}

/** Lowercase and strip accents, so "deposito" finds "depósito" — people type
 *  Spanish on English keyboards and phones drop the tilde all the time. */
function fold(text) {
  return text.toLowerCase().normalize('NFD').replace(/[̀-ͯ]/g, '');
}

/** Loose text match over title, tagline and keywords, ignoring accents. */
export function searchArticles(query) {
  const q = fold(query.trim());
  if (!q) return [];
  const terms = q.split(/\s+/);
  return ARTICLES.filter((a) => {
    const hay = fold(`${a.title} ${a.tagline} ${a.keywords} ${a.category}`);
    return terms.every((t) => hay.includes(t));
  });
}
