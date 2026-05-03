-- DakPro Academy — seed.sql v2
-- NL cursussen: Bitumineuze roofing (SBS/APP/Groendak/Renovatie) + Leien
-- Techniek: PVC-buis 80-100mm als aandrukrol
-- Foto mapping: /images/thumb_plat-overzicht.jpg, /images/thumb_leien-eindresultaat.jpg

INSERT OR IGNORE INTO users (email, name) VALUES
  ('demo@dakpro.nl', 'Jan de Groot'),
  ('test@dakpro.nl', 'Maria Jansen');

-- ═══════════════════════════════════════════════════════════
-- CURSUS 1 — Bitumineuze dakbedekking (roofing)
-- ═══════════════════════════════════════════════════════════
INSERT OR IGNORE INTO courses (id, title, description, lang, price_eur) VALUES
  ('kurs-roofing-nl',
   'Bitumineuze dakbedekking',
   'SBS, APP, groendak en renovatielagen — van materiaalkennis tot professionele verwerking op het dak.',
   'nl', 8900);

INSERT OR IGNORE INTO stages (id, course_id, title, position) VALUES
  ('rf-s1', 'kurs-roofing-nl', 'Soorten roofing: SBS, APP, Groendak',  1),
  ('rf-s2', 'kurs-roofing-nl', 'Verwerkingstechnieken',                  2),
  ('rf-s3', 'kurs-roofing-nl', 'Renovatie met ventilerende laag',        3),
  ('rf-s4', 'kurs-roofing-nl', 'Kwaliteitscontrole & eindexamen',        4);

-- Stage 1 lessen
INSERT OR IGNORE INTO lessons (id, stage_id, title, type, content, duration_min, position, is_free_preview) VALUES

('rf-s1-l1', 'rf-s1', 'Introductie bitumineuze dakbedekking', 'video',
'<p>Bitumineuze dakbedekking (roofing) is de meest gebruikte waterdichting voor platte en licht hellende daken. De basis is bitumen gemodificeerd met polymeren. Er bestaan twee fundamentele types: <strong>SBS</strong> (elastomeer) en <strong>APP</strong> (plastomeer).</p>',
9, 1, 1),

('rf-s1-l2', 'rf-s1', 'SBS roofing — eigenschappen en toepassing', 'text',
'<h3>SBS: Styreen-Butadieen-Styreen</h3>
<p>SBS is een elastomeer-gemodificeerd bitumen. Het heeft rubber-achtige eigenschappen: flexibel tot -25°C, keert terug naar oorspronkelijke vorm na vervorming. Dit maakt het ideaal voor het Belgische klimaat met grote temperatuurverschillen.</p>
<h3>Drager</h3>
<p>Polyester composiet (beste scheurweerstand) of glasvlies (dimensionsstabiel). Polyester wordt aanbevolen voor de toplaag.</p>
<h3>Verwerking</h3>
<p>SBS kan verwerkt worden met brander OF koudelijm. De toplaag is afgewerkt met leisteengranulaat (UV-bescherming) of vlak oppervlak.</p>
<h3>Voorbeelden</h3>
<p>Soprema Sopralene Flam, Icopal Poly Top, Imperbel Vedatop.</p>',
0, 2, 1),

('rf-s1-l3', 'rf-s1', 'APP roofing — wanneer en hoe toepassen', 'text',
'<h3>APP: Atactisch Polypropyleen</h3>
<p>APP is een plastomeer-gemodificeerd bitumen. In tegenstelling tot SBS gedraagt APP zich als een thermoplast: hard, niet elastisch, uitstekend bestand bij hoge temperaturen (tot +130°C).</p>
<h3>Wanneer APP kiezen?</h3>
<p>APP is ideaal bij intensieve zonblootstelling, warme klimaten en industriele toepassingen. In Belgie wordt SBS vaker gekozen vanwege het klimaat.</p>
<h3>Kritisch verschil: ALTIJD brander</h3>
<p>APP kan <strong>nooit</strong> met koudelijm worden aangebracht — altijd brander verwerking. De verwerkingstemperatuur is hoger dan bij SBS. Een goed gesmolten APP naad glinstert en is volledig homogeen.</p>
<h3>Herkenning</h3>
<p>APP heeft een gladdere, hardere onderzijde dan SBS. SBS voelt "rubbery" aan. Controleer altijd het productlabel.</p>',
0, 3, 0),

('rf-s1-l4', 'rf-s1', 'Groendak roofing — Sopralene Optima Garden', 'text',
'<h3>Roofing voor groendaken</h3>
<p>Een groendak vereist een speciale toplaag: <strong>worteldoorgroeibestendig</strong>. Gewone SBS of APP wordt op termijn doorprikt door plantenwortels.</p>
<h3>Sopralene Optima Garden 4 GF C3 FR (Soprema)</h3>
<ul>
  <li>Materiaal: SBS gemodificeerd bitumen met wortelwerende additieven</li>
  <li>Drager: polyester composiet</li>
  <li>Bovenzijde: zwart granulaat</li>
  <li>Dikte: 4 mm, breedte 1 m, lengte 8 m</li>
  <li>Brandvertragend (FR)</li>
  <li>Certificaten: CE + ATG Belgie</li>
  <li>Worteldoorgroeibestendig: ja (EN 13948)</li>
</ul>
<h3>Groendak opbouw van onder naar boven</h3>
<p>Draagvloer → dampscherm → isolatie → <strong>wortelwerende toplaag</strong> → filtervlies → drainagelaag → substraat → begroeiing.</p>
<p><strong>Nooit</strong> gewone roofing gebruiken op een groendak!</p>',
0, 4, 0),

('rf-s1-q1', 'rf-s1', 'Tussentoets — Soorten roofing', 'quiz', NULL, 0, 5, 0);

-- Stage 2 lessen
INSERT OR IGNORE INTO lessons (id, stage_id, title, type, content, duration_min, position, is_free_preview) VALUES

('rf-s2-l1', 'rf-s2', 'Professioneel aandrukken: de PVC-buis methode', 'video',
'<h3>Waarom een PVC-buis van 80-100mm?</h3>
<p>De traditionele aandrukwals dekt maar een deel van de breedte. Professionele dakdekkers gebruiken een PVC-buis van 80-100mm diameter als aandrukrol.</p>
<h3>Werkwijze stap voor stap</h3>
<ol>
  <li>Rol de roofingbaan volledig op de PVC-buis.</li>
  <li>Verwarm de onderzijde van de baan met de brander terwijl je de buis voor je uitrolt.</li>
  <li>Plaats je voet op de PVC-buis: het lichaamsgewicht drukt de <strong>volledige breedte tegelijk</strong> aan.</li>
  <li>De buis verdeelt de druk gelijkmatig — bitumen spreidt zich perfect uit zonder luchtbellen.</li>
</ol>
<h3>Resultaat</h3>
<p>Betere hechting over de volledige breedte, geen losse zones of luchtbellen. Dit is de techniek die professionele dakdekkers gebruiken.</p>
<h3>Nadien</h3>
<p>Controleer alle randen en overlappingen met een spatel. Opnieuw verwarmen waar nodig.</p>',
12, 1, 0),

('rf-s2-l2', 'rf-s2', 'Brandergebruik en temperatuurcontrole', 'text',
'<h3>Correcte afstand en snelheid</h3>
<p>Houd de brander 20-30cm van het membraan. Beweeg gelijkmatig — niet te snel (onvoldoende hechting) en niet te langzaam (verbranding).</p>
<h3>SBS vs APP temperatuur</h3>
<p>SBS: lagere temperatuur, baan wordt glanzend en begint licht te vloeien. APP: hogere temperatuur vereist, volledig doorverwarmen voor goede hechting.</p>
<h3>Veiligheid</h3>
<p>Nooit werken met brander bij sterke wind zonder windscherm. Brandblusser altijd aanwezig. Gasleidingen voor gebruik controleren op lekkage.</p>',
0, 2, 0),

('rf-s2-l3', 'rf-s2', 'Overlappingen, naden en atties', 'text',
'<h3>Overlappingseisen</h3>
<p>Zijdelings: min. <strong>80 mm</strong>. Kopse einden: min. <strong>150 mm</strong>. Bij helling onder 5°: beide maten met 50% verhogen.</p>
<h3>Naden staggeren</h3>
<p>Bij tweelaagsysteem: naden van onderlaag en toplaag mogen <strong>nooit samenvallen</strong> — minimaal 300mm verschuiven.</p>
<h3>Atties: volledig doorbranden</h3>
<p>Aan alle atties en dakranden: volledige doorbranding, geen koude zones. Minimale opkant 150mm.</p>
<h3>Naadcontrole</h3>
<p>Trek met spatel langs alle naden direct na verwerking. Goed gesmolten naad laat niet los.</p>',
0, 3, 0),

('rf-s2-q1', 'rf-s2', 'Tussentoets — Verwerkingstechnieken', 'quiz', NULL, 0, 4, 0);

-- Stage 3 lessen: Renovatie
INSERT OR IGNORE INTO lessons (id, stage_id, title, type, content, duration_min, position, is_free_preview) VALUES

('rf-s3-l1', 'rf-s3', 'Renovatie: ventilerende onderlaag (DuO HT / Aero FC)', 'video',
'<h3>Renovatiesysteem — principe</h3>
<p>Bij een bestaand dak met nog structureel intact oud roofing kan een renovatiesysteem worden toegepast <strong>zonder verwijdering</strong> van de oude lagen.</p>
<h3>De ventilerende laag</h3>
<p>Er wordt slechts <strong>1 extra laag</strong> aangebracht: een ventilerende onderlaag (bv. Soprema DuO HT of Aero FC). Dit membraan heeft een geperforeerde of geribbelde onderzijde.</p>
<h3>Hoe wordt het aangebracht?</h3>
<p>De ventilerende laag wordt <strong>los gelegd of puntsgewijs bevestigd</strong> op de bestaande dakbedekking. De perforaties laten vocht en resterende waterdamp ontsnappen via de opkanten.</p>
<h3>Atties: uitzondering — volledig doorbranden</h3>
<p>Aan de atties en dakranden wordt de ventilerende laag <strong>volledig vastgebrand</strong>. Hier mag geen losse zone zijn — waterdichte aansluiting is essentieel.</p>
<h3>Toplaag</h3>
<p>Op de ventilerende laag: gewone SBS of APP toplaag, volledig doorgebrand.</p>
<h3>Systeem samengevat</h3>
<ol>
  <li>Bestaand dak (wordt niet verwijderd)</li>
  <li>Ventilerende laag DuO HT/Aero FC — los/puntsgewijs + volledig gebrand aan atties</li>
  <li>Toplaag SBS of APP — volledig doorgebrand</li>
</ol>',
14, 1, 0),

('rf-s3-l2', 'rf-s3', 'Inspectie en voorbereiding voor renovatie', 'text',
'<h3>Inspectie bestaand dak</h3>
<p>Controleer voor aanvang op: blaren, scheuren, loshechting, staand water, beschadigde opkanten. Lokale defecten repareren voor start renovatie.</p>
<h3>Opkanten controleren</h3>
<p>Bestaande atties moeten schoon, droog en hecht zijn. Losse delen verwijderen. Hier wordt de nieuwe ventilerende laag volledig vastgebrand.</p>
<h3>Doorvoeren en details</h3>
<p>Alle dakdoorvoeren, koepelaansluitingen en randprofielen controleren en indien nodig vervangen voor start renovatie.</p>',
0, 2, 0),

('rf-s3-q1', 'rf-s3', 'Tussentoets — Renovatie', 'quiz', NULL, 0, 3, 0);

-- Stage 4: Eindexamen
INSERT OR IGNORE INTO lessons (id, stage_id, title, type, content, duration_min, position, is_free_preview) VALUES
('rf-s4-l1', 'rf-s4', 'Samenvatting en herhaling', 'video', '<p>Overzicht van alle lesstof ter voorbereiding op het eindexamen.</p>', 10, 1, 0),
('rf-s4-e1', 'rf-s4', 'EINDEXAMEN — Certificaat Bitumineuze dakbedekking', 'exam', NULL, 0, 2, 0);

-- Quiz vragen stage 1
INSERT OR IGNORE INTO quiz_questions (id, lesson_id, question, option_a, option_b, option_c, option_d, correct_index, position) VALUES
('rf-q1-1','rf-s1-q1','Wat is het fundamentele verschil tussen SBS en APP?','SBS is dikker','SBS is elastomeer, APP is plastomeer gemodificeerd','APP is goedkoper','SBS is voor warmere klimaten',1,1),
('rf-q1-2','rf-s1-q1','Tot welke temperatuur blijft SBS flexibel?','0C','-10C','-25C','-5C',2,2),
('rf-q1-3','rf-s1-q1','Kan APP roofing met koudelijm worden verwerkt?','Ja altijd','Alleen boven 15C','Nee, APP vereist altijd brander','Ja maar alleen onderlaag',2,3),
('rf-q1-4','rf-s1-q1','Waarom is gewone SBS niet geschikt voor een groendak?','Te dik','Niet worteldoorgroeibestendig','Te duur','Niet brandvertragend',1,4),
('rf-q1-5','rf-s1-q1','Welk Soprema product is gecertificeerd voor groendaken?','Sopralene Flam Torch','Sopralene Optima Garden 4 GF C3 FR','Icopal Poly Top','Vedatop SBS',1,5);

-- Quiz vragen stage 2
INSERT OR IGNORE INTO quiz_questions (id, lesson_id, question, option_a, option_b, option_c, option_d, correct_index, position) VALUES
('rf-q2-1','rf-s2-q1','Voordeel PVC-buis 80-100mm als aandrukrol?','Goedkoper dan wals','Gelijkmatige druk over volledige breedte','Snellere verwerking','Minder gewicht',1,1),
('rf-q2-2','rf-s2-q1','Minimale zijdelingse overlapping bij roofing?','5 cm','8 cm','10 cm','15 cm',1,2),
('rf-q2-3','rf-s2-q1','Minimale verschuiving naden onder- en toplaag?','10 cm','20 cm','30 cm','50 cm',2,3),
('rf-q2-4','rf-s2-q1','Hoe herken je een goed gesmolten SBS naad?','Droog en mat','Glanzend en licht gevloeid','Rookt sterk','Kleur veranderd',1,4),
('rf-q2-5','rf-s2-q1','Minimale opkant aan atties?','5 cm','10 cm','15 cm','20 cm',2,5);

-- Quiz vragen stage 3
INSERT OR IGNORE INTO quiz_questions (id, lesson_id, question, option_a, option_b, option_c, option_d, correct_index, position) VALUES
('rf-q3-1','rf-s3-q1','Hoeveel extra lagen bij een renovatiesysteem?','3 lagen','2 lagen','1 ventilerende laag + 1 toplaag','Alleen toplaag',2,1),
('rf-q3-2','rf-s3-q1','Hoe wordt de ventilerende laag op het bestaande dak gelegd?','Volledig doorgebrand','Los of puntsgewijs bevestigd','Mechanisch geschroefd','Koudelijm',1,2),
('rf-q3-3','rf-s3-q1','Hoe wordt de ventilerende laag AAN DE ATTIES bevestigd?','Ook los gelegd','Volledig doorgebrand','Niet bevestigd','Klemprofielen',1,3),
('rf-q3-4','rf-s3-q1','Functie perforaties in ventilerende onderlaag?','Gewichtsreductie','Betere hechting','Vocht/damp ontsnappen via opkanten','Decoratief',2,4),
('rf-q3-5','rf-s3-q1','Voorbeeld van een ventilerende renovatielaag?','Sopralene Optima Garden','Soprema DuO HT of Aero FC','Icopal Poly Top','Sopralene Flam',1,5);

-- Eindexamen vragen
INSERT OR IGNORE INTO quiz_questions (id, lesson_id, question, option_a, option_b, option_c, option_d, correct_index, position) VALUES
('rf-ex-1','rf-s4-e1','SBS staat voor?','Styreen-Butadieen-Styreen','Staal-Beton-Systeem','Synthetische Bitumen Samenstelling','Speciale Bitumen Standard',0,1),
('rf-ex-2','rf-s4-e1','Welk type roofing kan NOOIT met koudelijm?','SBS onderlaag','SBS toplaag','APP','Groendak membraan',2,2),
('rf-ex-3','rf-s4-e1','Voordeel PVC-buis methode?','Goedkoper','Gelijkmatige druk volledige breedte','Hogere snelheid','Minder gas',1,3),
('rf-ex-4','rf-s4-e1','Renovatie: hoe wordt de ventilerende laag op het dak gelegd?','Volledig doorgebrand','Los of puntsgewijs','Mechanisch geschroefd','Zelfklevend',1,4),
('rf-ex-5','rf-s4-e1','Renovatie aan atties: hoe hecht je de ventilerende laag?','Ook los','Volledig doorgebrand','Klemprofielen','Siliconen',1,5),
('rf-ex-6','rf-s4-e1','Minimale zijdelingse overlapping?','5 cm','8 cm','10 cm','12 cm',1,6),
('rf-ex-7','rf-s4-e1','Naden onder- en toplaag samenvallen is?','Toegestaan','Verboden, verhoogd lekkagerisico','Beter voor hechting','Maakt niet uit',1,7),
('rf-ex-8','rf-s4-e1','Hoe herken je APP van SBS op de werf?','APP is altijd rood','APP harder en gladdere onderzijde','SBS is zwaarder','Geen verschil',1,8),
('rf-ex-9','rf-s4-e1','Worteldoorgroeibestendigheid getest conform?','CE-markering','EN 13948','ISO 9001','BRL 4702',1,9),
('rf-ex-10','rf-s4-e1','Beste drager voor scheurweerstand toplaag?','Glasvlies','Polyester composiet','Aluminium folie','Kraftpapier',1,10);

-- ═══════════════════════════════════════════════════════════
-- CURSUS 2 — Leien dakbedekking
-- ═══════════════════════════════════════════════════════════
INSERT OR IGNORE INTO courses (id, title, description, lang, price_eur) VALUES
  ('kurs-lei-nl',
   'Leien dakbedekking',
   'Natuurleien: materiaalkennis, kwaliteitsklassen, legpatronen en professionele detaillering.',
   'nl', 9900);

INSERT OR IGNORE INTO stages (id, course_id, title, position) VALUES
  ('lei-s1', 'kurs-lei-nl', 'Materiaalkennis en kwaliteit',   1),
  ('lei-s2', 'kurs-lei-nl', 'Legpatronen en bevestiging',     2),
  ('lei-s3', 'kurs-lei-nl', 'Nok, goot en aansluitingen',     3),
  ('lei-s4', 'kurs-lei-nl', 'Eindexamen & diploma',           4);

INSERT OR IGNORE INTO lessons (id, stage_id, title, type, content, duration_min, position, is_free_preview) VALUES

('lei-s1-l1', 'lei-s1', 'Wat zijn natuurleien?', 'video',
'<h3>Definitie</h3>
<p>Natuurleien zijn metamorf gesteente (kleisteen omgevormd onder hoge druk en temperatuur) gewonnen in groeven en gekloofd langs natuurlijke splijtvlakken. Al eeuwenlang de meest duurzame dakbedekking.</p>
<h3>Herkomst — Belgische markt</h3>
<ul>
  <li><strong>Spanje (Galicie)</strong> — grootste producent, meest gebruikt in Belgie</li>
  <li><strong>Wales (UK)</strong> — hoge kwaliteit, premium segment</li>
  <li><strong>Duitsland (Mosel)</strong> — grijs-groene Rijnlandse leien</li>
  <li><strong>Frankrijk (Angers/Trelaze)</strong> — blauwgrijze leien</li>
</ul>',
8, 1, 1),

('lei-s1-l2', 'lei-s1', 'Kwaliteitsklassen EN 12326', 'text',
'<h3>Europese norm EN 12326</h3>
<p>De kwaliteit wordt bepaald door drie parameters:</p>
<h3>T-klasse: carbonaatgehalte</h3>
<ul>
  <li><strong>T1</strong> — max. 0,3% carbonaat (beste, meest duurzaam)</li>
  <li><strong>T2</strong> — tot 0,6% carbonaat</li>
  <li><strong>T3</strong> — tot 1,2% carbonaat (minder geschikt voor vochtig klimaat)</li>
</ul>
<h3>W-klasse: waterabsorptie</h3>
<ul>
  <li><strong>W1</strong> — minder dan 0,3% (beste)</li>
  <li><strong>W2</strong> — 0,3 tot 0,5%</li>
</ul>
<h3>Aanbeveling voor Belgie</h3>
<p>T1/W1 is de aanbevolen kwaliteit voor het Belgische klimaat. Spaanse leien van erkende producenten halen dit standaard.</p>',
0, 2, 1),

('lei-s1-q1', 'lei-s1', 'Tussentoets — Materiaalkennis', 'quiz', NULL, 0, 3, 0),

('lei-s2-l1', 'lei-s2', 'Ekoderdecking: berekening en uitvoering', 'video',
'<h3>Ekoderdecking — meest gebruikte methode in Belgie</h3>
<p>Enkelvoudige schubdekking waarbij elke lei wordt bedekt door de rij erboven. Toegestaan vanaf helling 25 graden.</p>
<h3>Berekening dekking</h3>
<p>Overlapping afhankelijk van helling: bij 25-35 graden minimaal 7,5 cm; bij 35-55 graden minimaal 6,0 cm; boven 55 graden minimaal 5,0 cm.</p>
<h3>Bevestiging</h3>
<p>Elke lei: 2 roestvrije klampen of koperen spijkers. Nooit stalen of gegalvaniseerde spijkers — die roesten en laten de lei los.',
13, 1, 0),

('lei-s2-l2', 'lei-s2', 'Dubbele dekking vs. Ekoderdecking', 'text',
'<h3>Dubbele dekking</h3>
<p>Elke lei bedekt door twee rijen. Verplicht bij helling onder 25 graden, hoge windbelasting of historische gebouwen. Gewicht: 45-60 kg/m2.</p>
<h3>Ekoderdecking</h3>
<p>Elke lei bedekt door een rij. Geschikt vanaf 25 graden. Gewicht: 25-35 kg/m2. Minder materiaal, snellere uitvoering.</p>
<h3>Praktisch verschil</h3>
<p>Draagstructuur dimensioneren op het gewicht! Dubbele dekking is bijna dubbel zo zwaar als Ekoderdecking.</p>',
0, 2, 0),

('lei-s2-q1', 'lei-s2', 'Tussentoets — Legpatronen', 'quiz', NULL, 0, 3, 0),

('lei-s3-l1', 'lei-s3', 'Nok, goot en muuraaansluitingen', 'video',
'<h3>Nok</h3>
<p>Afwerking met lood (klassiek, meest duurzaam), zink of nokpannen. Loodwerk: minimaal 200mm aan elke zijde.</p>
<h3>Gootaansluiting</h3>
<p>Leien hangen 30-50mm over de goot. Loodstrook of zinken waterkeerlijst verhindert opspatten.</p>
<h3>Rakwerk (muuraaansluiting)</h3>
<p>Aansluitingen aan verticale wanden: lood ingeklopt in voegen (ingeslagen lood) of loodflitsen. Minimale opkant 150mm.</p>',
11, 1, 0),

('lei-s3-q1', 'lei-s3', 'Tussentoets — Details', 'quiz', NULL, 0, 2, 0),
('lei-s4-e1', 'lei-s4', 'EINDEXAMEN — Certificaat Leien dakbedekking', 'exam', NULL, 0, 1, 0);

-- Quiz leien s1
INSERT OR IGNORE INTO quiz_questions (id, lesson_id, question, option_a, option_b, option_c, option_d, correct_index, position) VALUES
('lei-q1-1','lei-s1-q1','Grootste leverancier leien voor Belgie?','Wales','Duitsland','Spanje','Frankrijk',2,1),
('lei-q1-2','lei-s1-q1','Welke norm regelt kwaliteit natuurleien?','EN 13707','EN 12326','EN 14909','NEN 6068',1,2),
('lei-q1-3','lei-s1-q1','T1 betekent?','Max 0,3% carbonaat','Min 1% carbonaat','Testklasse 1','Thermische klasse 1',0,3),
('lei-q1-4','lei-s1-q1','Beste W-klasse voor vochtig klimaat?','W3','W2','W1','W0',2,4),
('lei-q1-5','lei-s1-q1','Hoe worden leien gekloofd?','Zaagmachine','Langs de natuurlijke splijtvlakken','Waterstraal','Chemisch',1,5);

-- Quiz leien s2
INSERT OR IGNORE INTO quiz_questions (id, lesson_id, question, option_a, option_b, option_c, option_d, correct_index, position) VALUES
('lei-q2-1','lei-s2-q1','Minimale helling voor Ekoderdecking?','15 graden','20 graden','25 graden','30 graden',2,1),
('lei-q2-2','lei-s2-q1','Verboden bevestiging bij leien?','Koperen spijkers','RVS klampen','Gegalvaniseerde stalen spijkers','Titanium klampen',2,2),
('lei-q2-3','lei-s2-q1','Hoeveel klampen per lei bij Ekoderdecking?','1','2','3','4',1,3);

-- Quiz leien s3
INSERT OR IGNORE INTO quiz_questions (id, lesson_id, question, option_a, option_b, option_c, option_d, correct_index, position) VALUES
('lei-q3-1','lei-s3-q1','Minimale opkant muuraaansluiting?','80 mm','100 mm','150 mm','200 mm',2,1),
('lei-q3-2','lei-s3-q1','Meest duurzaam materiaal voor nok?','Siliconen','PVC nokpan','Loodwerk','Aluminium tape',2,2);

-- Eindexamen leien
INSERT OR IGNORE INTO quiz_questions (id, lesson_id, question, option_a, option_b, option_c, option_d, correct_index, position) VALUES
('lei-ex-1','lei-s4-e1','Ekoderdecking is?','Dubbele dekking','Enkelvoudige schubdekking','Dakpannensysteem','Leien zonder overlapping',1,1),
('lei-ex-2','lei-s4-e1','Kwaliteitsklasse met laagste carbonaatgehalte?','T3','T2','T1','T0',2,2),
('lei-ex-3','lei-s4-e1','Minimale overhang leien boven goot?','10 mm','20 mm','30-50 mm','60 mm',2,3),
('lei-ex-4','lei-s4-e1','Waarom geen stalen spijkers bij leien?','Te duur','Roesten en laten lei los','Te zwaar','Niet beschikbaar',1,4),
('lei-ex-5','lei-s4-e1','Gewicht dubbele dekking vs Ekoderdecking?','Gelijk','Dubbele 45-60 kg/m2, Ekoder 25-35 kg/m2','Ekoder is zwaarder','Geen verschil',1,5),
('lei-ex-6','lei-s4-e1','Welk land heeft hoogste kwaliteitsreputatie leien?','Spanje','Wales','Duitsland','Portugal',1,6);

-- ═══════════════════════════════════════════════════════════
-- CURSUS 3 — Veiligheid op het dak (VGM) — preview only
-- ═══════════════════════════════════════════════════════════
INSERT OR IGNORE INTO courses (id, title, description, lang, price_eur) VALUES
  ('kurs-vgm-nl','Veiligheid op het dak (VGM)',
   'BHV, persoonlijke bescherming, valbeveiliging en wettelijke verplichtingen.','nl', 7900);

INSERT OR IGNORE INTO stages (id, course_id, title, position) VALUES
  ('vgm-s1', 'kurs-vgm-nl', 'Persoonlijke bescherming', 1),
  ('vgm-s2', 'kurs-vgm-nl', 'Valbeveiliging en wetgeving', 2);

INSERT OR IGNORE INTO lessons (id, stage_id, title, type, content, duration_min, position, is_free_preview) VALUES
('vgm-s1-l1','vgm-s1','Introductie VGM op het dak','video',
'<p>Daken behoren tot de gevaarlijkste werkomgevingen. In Belgie is een valpartij van meer dan 2 meter meldingsplichtig. Leer de meest voorkomende risicos kennen.</p>',
6,1,1),
('vgm-s1-l2','vgm-s1','Persoonlijke beschermingsmiddelen','text',
'<p>Verplichte PBM: harnasgordel type C, veiligheidshelm, veiligheidsschoenen S3, reflecterend vest. Elk PBM: CE-gecertificeerd en regelmatig geInspecteerd.</p>',
0,2,1),
('vgm-s1-l3','vgm-s1','Valbeveiliging systemen','video',NULL,9,3,0),
('vgm-s2-l1','vgm-s2','Arbo-wetgeving voor dakdekkers','text',NULL,0,1,0),
('vgm-s2-e1','vgm-s2','EINDEXAMEN — VGM Certificaat','exam',NULL,0,2,0);

-- ═══════════════════════════════════════════════════════════
-- Demo inschrijvingen
-- ═══════════════════════════════════════════════════════════
INSERT OR IGNORE INTO enrollments (user_email, course_id, activation_date, expiry_date) VALUES
  ('demo@dakpro.nl', 'kurs-roofing-nl', date('now'), date('now', '+365 days')),
  ('demo@dakpro.nl', 'kurs-lei-nl',     date('now'), date('now', '+365 days'));

INSERT OR IGNORE INTO lesson_progress (user_email, lesson_id) VALUES
  ('demo@dakpro.nl', 'rf-s1-l1'),
  ('demo@dakpro.nl', 'rf-s1-l2');
