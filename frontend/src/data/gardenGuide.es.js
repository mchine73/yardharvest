// La Guía del Huerto Comunitario — Spanish edition of gardenGuide.js, served
// at /es/about/guide. Pages/Guide.jsx picks this module when the page
// language is Spanish.
//
// KEEP IN SYNC with gardenGuide.js: identical exports, chapter order, slugs,
// icons and section/paragraph/list counts — only the human-readable text
// differs. gardenGuide.parity.test.js enforces it.
// Chapter titles/descriptions plus GUIDE_TITLE/GUIDE_DESCRIPTION are the
// source for the Spanish crawler meta in app/seo.py.
//
// Voice: tú, neutral Latin-American-leaning Spanish, warm and plain.
// "huerto" (never "jardín"), "parcela", "integrantes", "voluntariado".
// US institutions keep their real names with a short explanation; feet keep
// their figures with an approximate metric equivalent. No new facts.

export const GUIDE_TITLE = 'La Guía del Huerto Comunitario';
export const GUIDE_DESCRIPTION =
  'Una guía cercana y práctica para crear y llevar adelante un huerto ' +
  'comunitario: el terreno, el financiamiento, la construcción, la ' +
  'organización de los vecinos y cómo mantenerlo floreciente.';
export const GUIDE_INTRO =
  'Todo lo que sabemos sobre cómo crear y llevar adelante un huerto ' +
  'comunitario, desde el “¿a alguien más le interesa esto?” hasta un huerto ' +
  'lleno de vecinos y en plena producción. Está pensada para voluntarios de ' +
  'verdad, con trabajos de verdad: práctica, honesta y, de vez en cuando, ' +
  'llena de barro.';

export const CHAPTERS = [
  {
    slug: 'getting-started',
    title: 'Primeros pasos',
    icon: 'bi-flag',
    tagline: 'Del “¿no sería genial…?” a un plan de verdad.',
    description:
      'Cómo crear un huerto comunitario: mide el interés del vecindario, ' +
      'forma un equipo fundador y define una visión compartida antes de ' +
      'tocar una pala.',
    sections: [
      {
        h: 'Empieza por las personas, no por las plantas',
        p: [
          'Todo huerto comunitario empieza igual: alguien mira un terreno vacío y piensa “ahí podría haber tomates”. El truco está en averiguar quién más lo está pensando. Antes de investigar sobre suelos o semillas, investiga a tus vecinos. Un huerto con una tierra excelente y dos voluntarios fracasa; un huerto con una tierra mediocre y quince personas comprometidas encuentra la manera.',
          'Sondea el interés donde tu vecindario ya conversa: un volante en la cafetería, una publicación en el grupo del vecindario, un letrero con un número de teléfono en la cerca del propio terreno. Buscas dos cosas: una idea aproximada de cuántas personas querrían una parcela, y dos o tres personas dispuestas a ayudar a organizar. Esas personas organizadoras importan más que el número total.',
        ],
      },
      {
        h: 'Haz una reunión honesta',
        p: [
          'Reúne a las personas interesadas en una sala (o en un parque, o en un chat de grupo que con el tiempo se muda a una sala). Que la primera reunión sea corta y concreta. Quieres respuesta a tres preguntas: ¿Qué queremos: parcelas individuales, un huerto colectivo compartido o una mezcla? ¿Quién puede comprometer tiempo, y no solo entusiasmo? ¿Y cómo se ve el “éxito” dentro de un año?',
          'Escribe las respuestas. Eso se convierte en tu visión de una página, y te ahorrará discusiones más adelante. Cuando alguien proponga tener gallinas el segundo año, te alegrarás de haber dejado por escrito a qué se comprometió realmente el grupo.',
        ],
        list: [
          'Parcelas individuales: cada hogar cuida sus propias camas de cultivo. Es el modelo más común y el más fácil de organizar.',
          'Estilo comunal: todos trabajan camas compartidas y se reparten la cosecha. Ideal para huertos que abastecen a una despensa de alimentos, aunque exige una coordinación más firme.',
          'Mixto: parcelas individuales más algunas camas compartidas (hierbas aromáticas, flores, hileras para donar). Lo mejor de ambos mundos, y el modelo en el que terminan muchos huertos.',
        ],
      },
      {
        h: 'Dale al grupo un poquito de estructura',
        p: [
          'No necesitas estatutos para sembrar lechuga, pero sí tres funciones con nombre y apellido: alguien que hable con el dueño del terreno y con la ciudad, alguien que se encargue del dinero y alguien que lleve la lista de integrantes. En muchos huertos son dos personas repartiéndose las tres funciones, y está bien.',
          'Decide pronto cómo se toman las decisiones: con el voto de la mayoría en las reuniones basta. La meta no es la burocracia; es evitar que todo el huerto dependa de una sola persona heroica y agotada que, si cae, se lo lleva consigo. (Más sobre cómo evitar ese destino en el capítulo sobre cómo organizar a las personas.)',
        ],
      },
    ],
  },
  {
    slug: 'finding-land',
    title: 'Buscar terreno y planificar el espacio',
    icon: 'bi-geo-alt',
    tagline: 'Sol, agua, tierra y un apretón de manos que de verdad quede por escrito.',
    description:
      'Cómo encontrar terreno para un huerto comunitario, evaluar el sol, el ' +
      'agua y el suelo, y conseguir un arrendamiento o acuerdo que proteja el ' +
      'huerto.',
    sections: [
      {
        h: 'Cómo es un buen terreno',
        p: [
          'Las hortalizas son criaturas sencillas con tres exigencias: sol, agua y un suelo que no les sea abiertamente hostil. Busca al menos seis horas de sol directo (observa el terreno a distintas horas del día: ese lote tan agradable por la mañana puede pasar toda la tarde a la sombra de un edificio), una fuente de agua que puedas usar de forma legal y práctica, y un terreno razonablemente plano.',
          'La comodidad le gana a la perfección. Un terreno decente por el que la gente pasa a diario rendirá más que uno perfecto a diez minutos en auto. Los huertos viven de las visitas casuales —las de “paso un momento y riego”—, y la distancia las va apagando sin que nadie lo note.',
        ],
      },
      {
        h: 'Analiza el suelo antes de enamorarte',
        p: [
          'El suelo urbano tiene historia, y no toda es encantadora. Antes de comprometerte, haz un análisis de suelo: en la mayoría de los estados de EE. UU., las oficinas de extensión agrícola de las universidades (el servicio de asesoría que las universidades públicas ofrecen a la comunidad) los hacen a buen precio y, además de los nutrientes, revisan si hay plomo y otros contaminantes. Si aparece contaminación, no entres en pánico: las camas elevadas con tierra traída de fuera y una capa de barrera son la solución habitual y de sobra probada. Pero conviene saberlo antes de construir, no después.',
        ],
      },
      {
        h: '¿De quién es el terreno?',
        p: [
          'El sitio web de la oficina de tasación de tu condado (el county assessor, que registra y valora las propiedades) te dirá quién es dueño de cada predio. Los dueños suelen caer en tres grupos: la ciudad o el condado (a menudo lo más fácil: muchas ciudades tienen programas de terrenos baldíos o de “adopta un terreno”, y una persona cuyo trabajo es literalmente decirte que sí); iglesias, escuelas y organizaciones sin fines de lucro (que muchas veces están encantadas de acoger un huerto); y propietarios privados (de todo un poco, pero un huerto bien cuidado aumenta el valor de todo lo que lo rodea, y muchos propietarios lo saben).',
        ],
      },
      {
        h: 'Ponlo por escrito',
        p: [
          'Los huertos empiezan con un apretón de manos; sobreviven gracias a un acuerdo por escrito. Pide un contrato de arrendamiento o un acuerdo de uso de al menos tres años: estás por invertir dinero de verdad en tierra y camas de cultivo, y una sola temporada no alcanza para recuperarlo. El acuerdo debe cubrir quién paga el agua, qué pasa si el dueño vende, qué se espera en cuanto a responsabilidad civil y seguros, y qué significa “dejar el terreno limpio” si el acuerdo termina.',
          'Muchos huertos funcionan con un arrendamiento simbólico: un dólar al año es toda una tradición. Lo que importa no es la renta, sino que todos conozcan las reglas antes de construir la primera cama de cultivo.',
        ],
      },
    ],
  },
  {
    slug: 'funding-and-budget',
    title: 'Financiamiento y tu primer presupuesto',
    icon: 'bi-piggy-bank',
    tagline: 'De dónde sale el dinero y adónde se va sin hacer ruido.',
    description:
      'Costos de arranque de un huerto comunitario, presupuestos realistas, ' +
      'cuotas de parcela, subvenciones, ideas para recaudar fondos y el ' +
      'patrocinio fiscal, explicados de forma sencilla.',
    sections: [
      {
        h: 'Cuánto cuesta de verdad un huerto',
        p: [
          'El arranque es la parte cara: tierra y composta, madera para las camas, una conexión de agua o un tanque, herramientas básicas, un cobertizo o una caja para guardar herramientas, y una cerca si en tu vecindario la honestidad necesita un empujoncito. Según el tamaño y cuánto consigas regalado o de segunda mano, el primer año suele costar desde unos cientos de dólares para una construcción voluntaria y austera hasta varios miles para un terreno más grande, cercado y con una tubería de agua nueva; la tubería suele ser el gasto más grande de todos.',
          'Después del primer año, todo sale mucho más barato. Los gastos recurrentes son las facturas del agua, reponer composta, reemplazar herramientas, el seguro si lo tienes y algún candado nuevo cuando alguien pierde la llave. Otra vez. (Compra un candado de combinación.)',
        ],
      },
      {
        h: 'Cuotas de parcela: el motor constante',
        p: [
          'La mayoría de los huertos con parcelas cobran cuotas por temporada o anuales, y muchos se sostienen solo con ellas. Fija las cuotas para cubrir tus gastos recurrentes reales divididos entre el número de parcelas, con un margen; y ofrece siempre una tarifa reducida o la exención a quien la necesite, a cambio de horas de voluntariado si quieres. Un huerto que nadie puede pagar no es un huerto comunitario.',
          'Cobra las cuotas una sola vez, con una fecha límite clara y una consecuencia clara (sin pago no hay renovación y la parcela pasa a la lista de espera). Perseguir a once personas por veinte dólares cada una en pleno julio es justo la tarea que hace renunciar a los tesoreros.',
        ],
      },
      {
        h: 'Subvenciones, patrocinadores y el truco del patrocinador fiscal',
        p: [
          'Las pequeñas subvenciones para huertos comunitarios abundan más de lo que crees: las ofrecen los programas vecinales de la ciudad, las fundaciones comunitarias, las cadenas de ferreterías y de supermercados, las asociaciones de Master Gardeners (voluntarios formados en horticultura por las universidades) y las organizaciones sin fines de lucro dedicadas a la salud. La mayoría son modestas —piensa en cientos de dólares o unos pocos miles—, que resulta ser justo lo que necesita un huerto.',
          'Muchos financiadores exigen que el dinero lo reciba una organización sin fines de lucro. No hace falta que te conviertas en una 501(c)(3) (la figura de organización sin fines de lucro exenta de impuestos en EE. UU.): busca un patrocinador fiscal, es decir, una organización sin fines de lucro que ya exista (una iglesia, una asociación de vecinos, un banco de alimentos) y que reciba la subvención en tu nombre, normalmente a cambio de un pequeño porcentaje para gastos administrativos. Es un arreglo normal, aburrido y maravilloso.',
          'Y nunca subestimes las donaciones en especie: madererías con tablas algo torcidas pero perfectamente útiles, servicios de poda con astillas de madera gratis, restaurantes con cubetas. Los mejores presupuestos de huerto son mitad dinero y mitad encanto.',
        ],
      },
    ],
  },
  {
    slug: 'building-the-garden',
    title: 'Construir el huerto',
    icon: 'bi-hammer',
    tagline: 'Diseño, camas de cultivo, agua y la legendaria jornada de construcción.',
    description:
      'Cómo diseñar la distribución de un huerto comunitario, construir camas ' +
      'elevadas, instalar el agua y organizar una jornada de construcción con ' +
      'voluntarios que la gente disfrute.',
    sections: [
      {
        h: 'Dibuja antes de cavar',
        p: [
          'Dibuja el terreno a una escala aproximada y ubica primero lo grande: camas de cultivo, caminos, tomas de agua, composta, almacenamiento y un lugar para reunirse. Los caminos entre las camas deben dejar pasar una carretilla (tres pies, unos 90 cm, es cómodo; cuatro pies, unos 120 cm, es generoso), y al menos los caminos principales deben ser lo bastante anchos y firmes para sillas de ruedas y carritos de bebé: la accesibilidad sale mucho más barata si la diseñas desde el principio que si la agregas después.',
          'Pon los composteros donde el viento no te traiga el olor, el cobertizo donde no les haga sombra a las camas, y una banca en algún lugar desde donde se vea todo. La banca no es opcional. En la banca es donde ocurre la parte “comunitaria”.',
        ],
      },
      {
        h: 'Camas: elevadas o a ras de suelo',
        p: [
          'Las camas elevadas cuestan más al principio, pero resuelven varios problemas a la vez: un suelo dudoso, el drenaje, los límites entre parcelas y las espaldas que ya no se doblan como antes. Las hileras directamente en el suelo son casi gratis y funcionan bien donde el análisis salió limpio. Muchos huertos combinan las dos.',
          'Una cama elevada estándar mide cuatro pies de ancho (unos 120 cm, para alcanzar el centro desde ambos lados sin pisarla) y de ocho a doce pies de largo (unos 240 a 370 cm). El cedro sin tratar es el que más dura; el pino sin tratar es más barato y aun así aguanta varios años. Olvídate de los durmientes de vía de tren viejos y de cualquier madera tratada antes de que nacieras.',
        ],
      },
      {
        h: 'Agua: resuélvela bien, y una sola vez',
        p: [
          'Nada decide el éxito de un huerto tan silenciosamente como tener el agua a mano. Si los integrantes tienen que cargar bidones desde una llave lejana, para agosto las camas estarán secas. Procura que una manguera llegue a cada parcela: unas cuantas llaves bien ubicadas o un distribuidor sencillo con temporizadores. Si pagas el agua por medidor, cubre bien la tierra con acolchado y riega a fondo pero con poca frecuencia; tu factura y tus tomates te lo agradecerán.',
        ],
      },
      {
        h: 'La jornada de construcción',
        p: [
          'Junta el trabajo pesado en una o dos jornadas de voluntariado bien organizadas. La fórmula: deja todo cortado y preparado de antemano, dale a cada persona que llegue una tarea inmediata, pon a alguien con confianza a cargo de cada estación (armar camas, acarrear tierra, trazar caminos), dale de comer a la gente y termina con algo visible: la primera cama sembrada, el letrero en su sitio. La gente olvida los brazos adoloridos; lo que recuerda es la foto.',
        ],
      },
    ],
  },
  {
    slug: 'organizing-people',
    title: 'Organizar a las personas',
    icon: 'bi-people',
    tagline: 'Acuerdos de parcela, listas de espera y cómo no agotar a quien fundó el huerto.',
    description:
      'Cómo organizar a los integrantes de un huerto comunitario: acuerdos de ' +
      'parcela, listas de espera, horas de voluntariado, estructura de ' +
      'liderazgo y cómo evitar que se agote quien coordina.',
    sections: [
      {
        h: 'El acuerdo de parcela: una página, sin lenguaje de abogado',
        p: [
          'Cada integrante firma un acuerdo breve cuando recibe una parcela. Debe caber en una página y sonar como si lo hubiera escrito un vecino. Incluye cuánto cuestan las cuotas y cuándo se pagan; qué significa “mantener tu parcela” (sembrada antes de cierta fecha, sin maleza dentro de lo razonable, despejada al final de la temporada); qué se espera en las tareas compartidas; qué pasa con las parcelas abandonadas, y esas cosas pequeñas que se vuelven grandes: mascotas, niños, invitados, pesticidas o solo orgánico, y si los calabacines de la mesa junto a la cerca son de todos. (Lo son. Siempre lo son.)',
        ],
      },
      {
        h: 'Lleva la lista de espera en serio',
        p: [
          'Un buen huerto termina teniendo lista de espera, y una lista de espera es una promesa. Mantenla honesta: por orden de llegada (con las reglas de prioridad que hayan acordado, como dar preferencia a quienes viven en el vecindario), por escrito donde los organizadores puedan verla, y usándola de verdad cuando se libera una parcela. La forma más rápida de perder la confianza de la comunidad es que una parcela termine en manos del primo de alguien.',
          'Reasigna las parcelas abandonadas con rapidez pero con amabilidad: un mensaje cordial para ver cómo está la persona, una fecha límite clara y luego la reasignación. A quienes cultivan también les pasa la vida; el acuerdo que escribiste hace que esa conversación sea fácil en lugar de incómoda.',
        ],
      },
      {
        h: 'Reparte la carga antes de que aplaste a alguien',
        p: [
          'La causa más común de que un huerto comunitario muera no es la sequía ni el vandalismo: es el agotamiento de quien lo fundó. Una persona heroica lo hace todo durante tres años, se muda, y el huerto acaba hecho composta. Evítalo desde el primer día: rota cada año un par de funciones con responsable, mantén un documento compartido de cómo funcionan las cosas en realidad (dónde se guarda la llave del agua, cuándo se envían los avisos de cuotas, a quién llamar en la ciudad) y divide las tareas en partes pequeñas, cada una con su responsable, en lugar de un “todos ayudamos”, que casi siempre significa que no ayuda nadie.',
          'Pedir horas de voluntariado —unas pocas por temporada y por parcela, registradas de forma sencilla— mantiene cuidados los espacios compartidos sin tener que insistir. Combínalas con jornadas de trabajo programadas que terminen con comida. La asistencia se duplica cuando hay parrilla.',
        ],
      },
    ],
  },
  {
    slug: 'running-the-season',
    title: 'Gestionar la temporada',
    icon: 'bi-calendar3',
    tagline: 'Un año en la vida del huerto: cuotas, eventos, maleza y vuelta a empezar.',
    description:
      'Un ritmo, estación por estación, para llevar un huerto comunitario: ' +
      'renovaciones, arranque de primavera, mantenimiento de verano, eventos ' +
      'y preparación para el invierno.',
    sections: [
      {
        h: 'Fines del invierno: temporada de papeleo',
        p: [
          'La temporada empieza antes de que se descongele la tierra. Envía los avisos de renovación con una fecha límite real, cobra las cuotas, ofrece las parcelas libres a la lista de espera y pide la composta y las semillas del año mientras todo está barato y hay existencias. Una reunión de planificación ahora —con las fechas del arranque, las jornadas de trabajo y la limpieza de otoño— le da columna vertebral a todo el año.',
        ],
      },
      {
        h: 'Primavera: el arranque',
        p: [
          'Abre la temporada con un evento, no con un correo. Una jornada de trabajo para arrancar la primavera —camas renovadas, agua abierta, integrantes nuevos presentados y con un recorrido para que sepan dónde está todo— marca el tono y detecta los problemas (una llave rajada, la esquina podrida de una cama) mientras todavía salen baratos. Entrega a cada integrante nuevo su parcela asignada, el acuerdo de una página y un vecino con experiencia a quien hacerle preguntas.',
        ],
      },
      {
        h: 'Verano: mantén la máquina en marcha',
        p: [
          'El verano es casi todo maravilla y un poco de maleza. Los espacios compartidos del huerto necesitan un ritmo ligero y constante: una jornada de trabajo al mes, una rotación sencilla de tareas para cortar el pasto y voltear la composta, y alguien que le eche un vistazo al sistema de agua cada semana. La verdadera tarea es la comunicación: una nota mensual (qué está pasando, qué hay que hacer, qué está listo para cosechar) mantiene conectados a los integrantes menos activos y le recuerda a todo el mundo, sin hacer ruido, que el huerto está vivo y que alguien lo guía.',
          'Organiza al menos un evento puramente social. Una cata de tomates, una comida compartida con lo cosechado, una búsqueda del tesoro para niños: cualquier cosa en la que nadie tenga que quitar maleza. Los huertos que solo se reúnen para trabajar acaban dejando de reunirse.',
        ],
      },
      {
        h: 'Otoño: un aterrizaje suave',
        p: [
          'Cierra la temporada a propósito: un día de limpieza con expectativas claras (parcelas despejadas antes de cierta fecha, herramientas inventariadas, agua drenada antes de la primera helada), ajo y cultivos de cobertura sembrados para quien los quiera, y una nota breve de cierre: qué creció bien, qué se rompió, qué cambiar. Luego deja que todos descansen. Tú también.',
        ],
      },
    ],
  },
  {
    slug: 'harvest-and-impact',
    title: 'Cosecha e impacto',
    icon: 'bi-basket',
    tagline: 'Contar zanahorias, compartir excedentes y demostrar que vale la pena.',
    description:
      'Cómo registrar la cosecha y el impacto de un huerto comunitario: ' +
      'programas de donación, registros sencillos y reportes que convencen a ' +
      'financiadores y ciudades.',
    sections: [
      {
        h: '¿Para qué contar?',
        p: [
          'No necesitas datos para disfrutar un tomate. Sí los necesitas el día en que la ciudad pregunta si el huerto “de verdad se usa”, o una solicitud de subvención pide resultados, o un vecino escéptico dice que es “solo un terreno de pasatiempo”. Un huerto que puede decir a cuántos hogares alimenta, cuántas libras cosechó y cuántas horas de voluntariado registró es un huerto muy difícil de rebatir… y muy fácil de financiar.',
        ],
      },
      {
        h: 'Que registrar no cueste casi nada',
        p: [
          'El mejor sistema de registro es el que la gente de verdad usa. Una báscula junto al cobertizo y un registro sencillo —una hoja en una tabla con clip o un formulario compartido— te llevan sorprendentemente lejos. Registra tres cosas: el peso de la cosecha (aunque sean estimaciones aproximadas), las horas de voluntariado y la participación (parcelas ocupadas, largo de la lista de espera, asistencia a los eventos). Cinco segundos por canasta de cosecha es todo lo que pides.',
        ],
      },
      {
        h: 'Comparte los excedentes',
        p: [
          'Tarde o temprano, todo huerto produce más de lo que sus integrantes pueden comer: casi siempre de golpe, y casi siempre calabacines. Pon esos excedentes a trabajar: una cama de cultivo destinada a donaciones o un programa de “siembra una hilera de más” (grow a row), una entrega semanal fija a una despensa de alimentos local (llama antes: te dirán qué pueden recibir y cuándo), o la humilde mesa para compartir junto a la entrada. Pesa lo que donas: las libras donadas son la cifra más convincente del reporte anual de cualquier huerto.',
        ],
      },
      {
        h: 'Cuenta la historia una vez al año',
        p: [
          'Cada otoño, junta tus números en una sola página: libras cosechadas, libras donadas, hogares, horas de voluntariado y eventos realizados, más tres fotos y una cita de algún integrante. Envíala al dueño del terreno, a la ciudad, a tus financiadores y al grupo del vecindario. Esa sola página renueva arrendamientos, consigue subvenciones y llena la lista de espera de la próxima primavera: es la hora mejor invertida de todo el año.',
        ],
      },
    ],
  },
  {
    slug: 'troubleshooting',
    title: 'Resolver problemas',
    icon: 'bi-bandaid',
    tagline: 'Vándalos, parcelas vacías, conflictos y otros problemas con solución.',
    description:
      'Problemas comunes de los huertos comunitarios y cómo resolverlos: ' +
      'robos y vandalismo, parcelas abandonadas, conflictos entre integrantes, ' +
      'plagas y cambios de liderazgo.',
    sections: [
      {
        h: 'Robos y vandalismo',
        p: [
          'Pasa, duele y se supera. Las mejores defensas son sociales, no arquitectónicas: a un huerto que se ve querido y con movimiento lo molestan menos, los vecinos que conocen el huerto lo cuidan, y una mesa para compartir junto a la entrada convierte una cantidad sorprendente de “robos” en “llevarse las verduras gratis, tal como se invitaba”. Las cercas ayudan; los letreros con el nombre del huerto y de su gente ayudan más. Si se llevan algo, vuelve a sembrar con alegría y a la vista de todos: la resiliencia luce muy bien.',
        ],
      },
      {
        h: 'La parcela abandonada',
        p: [
          'La parcela de alguien se llenó de cardos y esa persona ya no contesta los mensajes. Tu acuerdo de parcela ya lo resolvió: un mensaje cordial, una fecha límite clara y la reasignación a la lista de espera. La versión amable importa: la razón número uno por la que se abandonan las parcelas es que la vida se puso difícil, no que la gente dejara de interesarse. Ofrece una salida digna y un lugar de nuevo en la lista, y aun así cumple los plazos. Las dos mitades son parte del trabajo.',
        ],
      },
      {
        h: 'Conflictos entre personas',
        p: [
          'Dos integrantes se pelean por un árbol que da sombra, una calabaza invasora o un rencor de hace diez años, anterior al huerto. No hagas de juez junto a la cerca. Ten un proceso fijo y aburrido: las quejas van a los organizadores, se conversan con calma con las dos personas y se resuelven según las reglas escritas, que para eso las escribiste. La mayoría de los conflictos en un huerto en realidad nacen de expectativas poco claras; cada pelea es una frase más para el acuerdo del año que viene.',
        ],
      },
      {
        h: 'Cuando alguien que lidera se va',
        p: [
          'Quienes coordinan se mudan, se agotan o simplemente cierran su capítulo. Si rotaste las funciones y mantuviste el documento de cómo funcionan las cosas del capítulo sobre organizar a las personas, esto es un relevo, no una crisis. Si no lo hiciste, hazlo ahora, mientras esa persona sigue por aquí y te tiene cariño. El conocimiento de un huerto debe vivir en una carpeta compartida, no en la cabeza de una sola persona.',
        ],
      },
      {
        h: 'Y cuando todo va de maravilla',
        p: [
          'El último problema, del que nadie te avisa: el éxito. Un huerto próspero atrae una lista de espera, solicitudes de eventos, una conversación con la ciudad sobre abrir un segundo terreno y más papeleo del que cualquier voluntario aceptó. Ese es el momento de organizarse en serio —registros claros, comunicación constante, cuotas que se cobran solas— para que el crecimiento del huerto funcione con sistemas en lugar de devorarse las tardes de una sola persona. Como sea que lo manejes, protege lo que hizo que funcionara: vecinos, con las manos en la tierra, juntos.',
        ],
      },
    ],
  },
];
