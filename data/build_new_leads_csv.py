"""One-off generator for the web-researched independent-garden prospect list.

Builds data/new_leads_research.csv in the /crm/import format:
    Name, City, State, Type, Website, Email, Contact, Phone, Tags, Notes

Every organization below was surfaced and verified via web research
(news articles, city/neighborhood grant approvals, garden directories) in
June 2026. Emails are included ONLY where actually published on the org's
official site/public listing — none are guessed. Deduped against the
existing 247 CRM seed leads (Denver Urban Gardens, Re:Vision, Cultivate KC,
and Sioux Falls Community Gardens were already present and are omitted).
"""
import csv
import os

LEADS = [
    # ---- Omaha, NE ----
    dict(Name="City Sprouts", City="Omaha", State="NE", Type="Independent",
         Website="https://www.omahasprouts.org/", Email="info@omahasprouts.org",
         Contact="Shannon Kyler", Phone="", Tags="Prospect, Omaha, Garden Network",
         Notes="Omaha's oldest community garden (est. 1995), a 501(c)(3) running ~45 plots plus the Decatur Urban Farm in North Omaha and a South Omaha site. Source: https://www.omahasprouts.org/"),
    dict(Name="The Big Garden", City="Omaha", State="NE", Type="Independent",
         Website="https://biggarden.org/", Email="contact@biggarden.org",
         Contact="", Phone="", Tags="Prospect, Omaha, Garden Network",
         Notes="Nonprofit network of 175-200+ community gardens across metro Omaha, Nebraska, Kansas and SW Iowa; annual intake season for new sites. Source: https://biggarden.org/contact-us"),
    dict(Name="No More Empty Pots", City="Omaha", State="NE", Type="Independent",
         Website="https://nmepomaha.org/", Email="ask@nmepomaha.org",
         Contact="Nancy Williams", Phone="", Tags="Prospect, Omaha",
         Notes="North Omaha food-security nonprofit (est. 2010) running a Florence food hub and community gardens; foundation-backed. Source: https://nmepomaha.org/who-we-are/frequent-questions.html"),
    dict(Name="Global Leadership Group Omaha", City="Omaha", State="NE", Type="Independent",
         Website="https://globalleadershipgroupomaha.org/", Email="globalleadershipgroupomaha@gmail.com",
         Contact="LaVonya Goodwin", Phone="", Tags="Prospect, Omaha, Grant Recipient",
         Notes="North Omaha nonprofit with a 25-bed plot-adoption garden at 3118 N 24th St; won a 2024 Omaha Neighborhood Grant ($5,000) for accessible beds. Source: https://globalleadershipgroupomaha.org/"),
    dict(Name="Gifford Park Neighborhood Association Community Garden", City="Omaha", State="NE", Type="Independent",
         Website="http://giffordparkomaha.org/Community_Garden.html", Email="",
         Contact="", Phone="", Tags="Prospect, Omaha, Neighborhood Assoc, Grant Recipient",
         Notes="Midtown community garden (est. 2001) near 35th & Cass with a youth garden program; won a 2024 Omaha Neighborhood Grant ($4,716). Source: https://omahafoundation.org/news/omaha-neighborhood-grants-award-80k-to-24-groups-for-community-building-in-2024-cycle/"),
    dict(Name="Miller Park Minne Lusa Neighborhood Association", City="Omaha", State="NE", Type="Independent",
         Website="https://mpml.org/", Email="",
         Contact="", Phone="", Tags="Prospect, Omaha, Neighborhood Assoc, Grant Recipient",
         Notes="North Omaha association running a community garden that donates harvests to pantries; won a 2024 Omaha Neighborhood Grant ($2,500). Source: https://omahafoundation.org/news/omaha-neighborhood-grants-award-80k-to-24-groups-for-community-building-in-2024-cycle/"),
    dict(Name="Hartman Avenue Neighborhood Association Community Garden", City="Omaha", State="NE", Type="Independent",
         Website="", Email="",
         Contact="", Phone="", Tags="Prospect, Omaha, Neighborhood Assoc, Grant Recipient",
         Notes="North Omaha garden behind Mount View Presbyterian Church (5308 Hartman Ave); won a 2024 Omaha Neighborhood Grant ($5,000) for expansion. Source: https://omahafoundation.org/news/omaha-neighborhood-grants-award-80k-to-24-groups-for-community-building-in-2024-cycle/"),
    dict(Name="Dahlman Garden Club", City="Omaha", State="NE", Type="Independent",
         Website="https://www.facebook.com/DahlmanGardenClub/", Email="",
         Contact="", Phone="", Tags="Prospect, Omaha, Grant Recipient",
         Notes="Community garden in Little Italy/Dahlman, South Omaha (6th & Pierce); won a 2024 Omaha Neighborhood Grant ($1,150) for rainwater capture and beds. Source: https://omahafoundation.org/news/omaha-neighborhood-grants-award-80k-to-24-groups-for-community-building-in-2024-cycle/"),
    dict(Name="Healing Roots Garden", City="Omaha", State="NE", Type="Independent",
         Website="", Email="",
         Contact="Clarice Dombeck", Phone="", Tags="Prospect, Omaha, Refugee/New American",
         Notes="African Diaspora co-op garden on N 24th St (est. 2021) worked by ~60 volunteers growing culturally significant crops. Source: https://www.unothegateway.com/the-history-of-north-omahas-healing-roots-garden/"),
    dict(Name="Free Farm Syndicate", City="Omaha", State="NE", Type="Independent",
         Website="https://www.instagram.com/freefarmsyndicate", Email="grassyndicate@gmail.com",
         Contact="Kourtney Wismont", Phone="", Tags="Prospect, Omaha",
         Notes="Volunteer urban-ag collective growing/giving away free produce at two Omaha lots (S 10th St, N 29th St). Source: https://el-perico.com/omahas-community-gardens-growing-strong/"),
    dict(Name="Refugee Women Organization of Nebraska (New American Urban Farm)", City="Omaha", State="NE", Type="Independent",
         Website="", Email="",
         Contact="Christine Ross", Phone="(402) 306-6651", Tags="Prospect, Omaha, Refugee/New American",
         Notes="Runs the New American Urban Farm at Cooper Farm (8502 Mormon Bridge Rd) where refugee/immigrant growers farm native-country produce. Source: https://el-perico.com/omahas-community-gardens-growing-strong/"),
    dict(Name="Latino Center of the Midlands", City="Omaha", State="NE", Type="Independent",
         Website="https://www.latinocenter.org/", Email="",
         Contact="Efren Garcia", Phone="(402) 733-2720", Tags="Prospect, Omaha",
         Notes="South Omaha nonprofit running a gardening/health program (Siembra Salud / Cultivate Wellness). Source: https://thereader.com/2022/08/08/for-some-latino-omahans-solving-health-disparities-starts-in-the-garden/"),

    # ---- Lincoln, NE ----
    dict(Name="Community Crops", City="Lincoln", State="NE", Type="Independent",
         Website="https://communitycrops.org/", Email="info@communitycrops.org",
         Contact="Ailyne Swartz Taylor", Phone="", Tags="Prospect, Lincoln, Garden Network",
         Notes="Lincoln's flagship community-gardens nonprofit — ~14 sites / ~19 acres serving 200+ growers; 2025 Lincoln Community Foundation operating support. Source: https://communitycrops.org/gardens/"),
    dict(Name="Southern Heights Food Forest", City="Lincoln", State="NE", Type="Independent",
         Website="https://southernheightsff.org/", Email="",
         Contact="", Phone="", Tags="Prospect, Lincoln, Grant Recipient",
         Notes="2-acre site at Southern Heights Presbyterian Church with Nebraska's first public food forest plus 50+ garden plots; 2024 Lincoln Community Foundation grant + $10k Nebraska Presbyterian Foundation. Source: https://southernheightsff.org/"),
    dict(Name="Arapahoe Garden (Southview Baptist Church)", City="Lincoln", State="NE", Type="Independent",
         Website="https://southviewbaptist.org/garden", Email="sarahhunter0505@gmail.com",
         Contact="Sarah Hunter", Phone="", Tags="Prospect, Lincoln, Neighborhood Assoc",
         Notes="Self-managed Indian Village neighborhood garden (opened 2013) with twenty 10x10 plots, run with Community CROPS. Source: https://southviewbaptist.org/garden"),
    dict(Name="Asian Community & Cultural Center", City="Lincoln", State="NE", Type="Independent",
         Website="https://www.lincolnasiancenter.org/", Email="",
         Contact="", Phone="", Tags="Prospect, Lincoln, Refugee/New American",
         Notes="Refugee/immigrant services nonprofit (144 N 44th St) co-running the BCBS Knyaw refugee garden for Lincoln's Karen community with Community Crops. Source: https://newsroom.nebraskablue.com/lincoln-communal-garden-growing/"),
    dict(Name="Prairie Pines (Wachiska Audubon Society)", City="Lincoln", State="NE", Type="Independent",
         Website="https://prairiepines.org/", Email="",
         Contact="", Phone="", Tags="Prospect, Lincoln, Refugee/New American",
         Notes="154-acre preserve NE of Lincoln (to Wachiska Audubon in 2024) hosting a 5-acre Community Crops incubator farm for new-American specialty-crop growers. Source: https://nebraskaexaminer.com/2024/10/24/lincoln-based-audubon-chapter-takes-on-ownership-management-of-nature-preserve/"),
    dict(Name="Matt Talbot Kitchen & Outreach (Hope Garden)", City="Lincoln", State="NE", Type="Independent",
         Website="https://www.mtko.org/", Email="",
         Contact="", Phone="", Tags="Prospect, Lincoln, Faith-based",
         Notes="Hunger/homeless-services nonprofit operating an on-site Hope Garden that feeds its kitchen and pantry. Source: https://www.mtko.org/"),
    dict(Name="Clinton Neighborhood Organization", City="Lincoln", State="NE", Type="Independent",
         Website="https://www.facebook.com/CNOLincoln", Email="",
         Contact="", Phone="", Tags="Prospect, Lincoln, Neighborhood Assoc, Grant Recipient",
         Notes="NE-Lincoln association running a community plant & seed exchange (29th & Holdrege); 2026 Lincoln Community Foundation Open Door grant. Source: https://lcf.org/helping-nonprofits/grants-awarded.html/article/2026/01/31/lincoln-community-foundation-2025-open-door-grants"),
    dict(Name="Cooper Park Community Garden", City="Lincoln", State="NE", Type="City-Sponsored",
         Website="https://www.lincoln.ne.gov/City/Departments/Parks-and-Recreation/Parks-Facilities/Parks-A-to-Z/Cooper-Park", Email="",
         Contact="", Phone="", Tags="Prospect, Lincoln, City Program",
         Notes="Garden at 1151 Centerpark Rd (est. 2011) via City of Lincoln + nonprofit partnership; reported 150+ plots plus orchard and composting. Source: https://www.travelnebraska.org/cities-and-towns/nebraska-community-gardens"),

    # ---- Des Moines, IA ----
    dict(Name="Lutheran Services in Iowa - Global Greens", City="Des Moines", State="IA", Type="Independent",
         Website="https://lsiowa.org/ircs/global-greens/", Email="",
         Contact="", Phone="", Tags="Prospect, Des Moines, Garden Network, Refugee/New American",
         Notes="Refugee/immigrant farming program with an 8.5-acre incubator farm plus metro garden plots; bought Dogpatch Urban Gardens in 2025 and manages the Drake Neighborhood garden. Source: https://www.iowapublicradio.org/ipr-news/2025-05-01/immigrant-refugee-farmers-global-greens-lutheran-services-of-iowa-lsi"),
    dict(Name="Joppa - Shared Roots Community Garden", City="Des Moines", State="IA", Type="Independent",
         Website="https://www.joppa.org/2020/11/06/introducing-shared-roots-community-garden/", Email="",
         Contact="", Phone="", Tags="Prospect, Des Moines",
         Notes="Nonprofit-run garden in Cheatom Park with 75 beds providing free produce; weekly 'Garden Thyme' sessions with master gardeners. Source: https://www.joppa.org/2020/11/06/introducing-shared-roots-community-garden/"),
    dict(Name="Watchmen Community Garden", City="Des Moines", State="IA", Type="Independent",
         Website="https://watchmen.ngo/watchmen-community-garden/", Email="infonow@watchmen.ngo",
         Contact="", Phone="", Tags="Prospect, Des Moines, Grant Recipient",
         Notes="Nonprofit 5,000 sq ft garden off Hickman Rd feeding the Watchmen Food Pantry; United Way of Central Iowa community-garden mini-grant recipient. Source: https://watchmen.ngo/watchmen-community-garden/"),
    dict(Name="Birds & Bees Urban Farm", City="Des Moines", State="IA", Type="Independent",
         Website="https://birdsbeesurbanfarm.org/", Email="kathy@birdsbeesurbanfarm.org",
         Contact="Kathy Byrnes", Phone="", Tags="Prospect, Des Moines",
         Notes="501(c)(3) educational urban farm in Sherman Hill (735 19th St); workshops, tours, and local-food-policy work with the City of Des Moines. Source: https://www.charitynavigator.org/ein/843414342"),
    dict(Name="Faith & Grace Garden (St. Timothy's Episcopal Church)", City="West Des Moines", State="IA", Type="Independent",
         Website="https://sttimothysiowa.org/faith-grace-garden/", Email="wdmmarshall@msn.com",
         Contact="Mark Marshall", Phone="", Tags="Prospect, Des Moines, Faith-based",
         Notes="All-organic donation garden (1020 24th St, WDM) that grew/donated ~32,370 lbs of produce in 2025 to DMARC and others; ~1,000 tomato plants. Source: https://sttimothysiowa.org/faith-grace-garden/"),
    dict(Name="Drake Neighborhood Community Garden", City="Des Moines", State="IA", Type="Independent",
         Website="https://dna.wildapricot.org/Drake-Neighborhood-Community-Garden", Email="info@drakeneighborhood.org",
         Contact="", Phone="", Tags="Prospect, Des Moines, Neighborhood Assoc",
         Notes="Neighborhood-association garden on 27th St with ~30 plots since the mid-1990s; now managed with LSI Global Greens. Source: https://dna.wildapricot.org/Drake-Neighborhood-Community-Garden"),
    dict(Name="Sweet Tooth Farm", City="Des Moines", State="IA", Type="Independent",
         Website="", Email="",
         Contact="Monika Owczarski", Phone="", Tags="Prospect, Des Moines",
         Notes="Urban market garden in River Bend (1809 8th St) supplying food pantries and community fridges; in 2026 seeking to buy its city-leased parcel. Source: https://www.axios.com/local/des-moines/2026/03/19/farm-owner-wants-to-save-her-garden-leased-from-dsm"),
    dict(Name="Eat Greater Des Moines", City="Des Moines", State="IA", Type="Independent",
         Website="https://www.eatgreaterdesmoines.org/", Email="info@eatgreaterdesmoines.org",
         Contact="", Phone="", Tags="Prospect, Des Moines, Garden Network",
         Notes="Food-systems nonprofit supporting 25+ school/community/faith gardens across the metro plus food rescue; key network hub and referral partner. Source: https://goodfoodorgguide.com/listing/eat-greater-des-moines/"),
    dict(Name="Oakridge Neighborhood", City="Des Moines", State="IA", Type="Independent",
         Website="https://oakridgeneighborhood.org/", Email="",
         Contact="", Phone="", Tags="Prospect, Des Moines",
         Notes="Nonprofit on 17 acres in the urban core running food-security programming (community fridge/pantry) with Eat Greater Des Moines. Source: https://www.changex.org/us/communityfridge/des-moines-ia-usa-polk-county-5"),
    dict(Name="Central Iowa Shelter & Services Urban Farm", City="Des Moines", State="IA", Type="Independent",
         Website="", Email="",
         Contact="", Phone="", Tags="Prospect, Des Moines",
         Notes="Shelter nonprofit running a downtown greenhouse/urban-farm job-training program growing food while helping adults re-enter the workforce. Source: https://iowacapitaldispatch.com/2020/10/03/iowa-sees-surge-in-urban-farming-as-pandemic-continues/"),
    dict(Name="Woodland Realm Community Garden", City="Des Moines", State="IA", Type="Independent",
         Website="https://www.facebook.com/dsm.dcg/", Email="",
         Contact="Ryan Francois", Phone="", Tags="Prospect, Des Moines",
         Notes="Half-acre community garden at 24th & High (started 2020) hosting community dinners and produce bazaars; won a city zoning battle to keep operating. Source: https://who13.com/news/metro-news/community-garden-finally-gets-win-vs-restrictive-city-ordinances/"),
    dict(Name="Des Moines Parks & Recreation Community Gardens", City="Des Moines", State="IA", Type="City-Sponsored",
         Website="https://www.dsm.city/departments/parks_and_recreation-division/places/community_gardens.php", Email="communitygarden@dmgov.org",
         Contact="", Phone="", Tags="Prospect, Des Moines, City Program",
         Notes="Municipal program managing 209 rentable plots (~$30/season) at Franklin Ave (179 raised beds) and Woodland Park, with a produce-donation requirement. Source: https://www.dsm.city/departments/parks_and_recreation-division/places/community_gardens.php"),

    # ---- Regional sweep (new only; dupes already in CRM removed) ----
    dict(Name="Kansas City Community Gardens", City="Kansas City", State="MO", Type="Independent",
         Website="https://kccg.org/", Email="contact@kccg.org",
         Contact="", Phone="(816) 931-3877", Tags="Prospect, Garden Network",
         Notes="501(c)(3) since 1985 supporting ~330 community gardens, 257 neighborhood orchards and 241 school gardens across the KC metro (MO & KS) — one of the largest networks in the US. Source: https://kccg.org/history-and-mission/"),
    dict(Name="Seed St. Louis", City="St. Louis", State="MO", Type="Independent",
         Website="https://seedstl.org/", Email="",
         Contact="Matthew Schindler", Phone="(314) 588-9600", Tags="Prospect, Garden Network",
         Notes="Formerly Gateway Greening; since 1984 supports 250+ community/school gardens and urban orchards across the St. Louis region plus a garden land trust. Source: https://seedstl.org/staff/"),
    dict(Name="Columbia Center for Urban Agriculture", City="Columbia", State="MO", Type="Independent",
         Website="https://www.columbiaurbanag.org/", Email="info@columbiaurbanag.org",
         Contact="", Phone="(573) 514-4174", Tags="Prospect",
         Notes="Nonprofit (501c3 since 2009) running Columbia's Agriculture Park and the Stevenson Veterans Urban Farm. Source: https://www.columbiaurbanag.org/"),
    dict(Name="Community Garden Coalition (Columbia/Boone County)", City="Columbia", State="MO", Type="Independent",
         Website="https://comogardens.org/", Email="",
         Contact="Lindsey Smith", Phone="", Tags="Prospect, Garden Network",
         Notes="Volunteer coalition supporting community gardens across Columbia/Boone County for 40+ years; 2025 report cites 450+ gardeners/family members. Source: https://comogardens.org/"),
    dict(Name="Sprout City Farms", City="Denver", State="CO", Type="Independent",
         Website="https://sproutcityfarms.org/", Email="info@sproutcityfarms.org",
         Contact="", Phone="(720) 239-2714", Tags="Prospect",
         Notes="Urban-ag nonprofit (since 2010) operating community farms incl. Denver Green School and Mountair Park community farms plus partner sites. Source: https://sproutcityfarms.org/our-story"),
    dict(Name="Youth Farm", City="Minneapolis", State="MN", Type="Independent",
         Website="https://youthfarmmn.org/", Email="",
         Contact="Gunnar Liden", Phone="", Tags="Prospect, Garden Network",
         Notes="Nonprofit since 1995, one of MN's first urban-farming orgs; runs ~10 farm/garden sites across North Minneapolis and St. Paul. Source: https://youthfarmmn.org/our-team/staff/"),
    dict(Name="Frogtown Farm", City="St. Paul", State="MN", Type="Independent",
         Website="https://www.frogtownfarm.org/", Email="",
         Contact="", Phone="", Tags="Prospect",
         Notes="Founded 2013; one of the largest certified-organic urban demonstration farms in the US (5-acre site in Frogtown Park & Farm). Source: https://www.frogtownfarm.org/"),
    dict(Name="Common Ground (Lawrence-Douglas County)", City="Lawrence", State="KS", Type="City-Sponsored",
         Website="https://www.dgcoks.gov/administration/sustainability/common-ground", Email="",
         Contact="", Phone="", Tags="Prospect, City Program, Garden Network",
         Notes="City program (est. 2012) with ~9.5 acres across ~10 sites (9 community gardens + incubator farm) serving 225+ gardeners. Source: https://www2.ljworld.com/news/general-news/2022/jul/28/common-ground-adding-11th-community-garden-in-lawrence/"),
    dict(Name="Groundwork Northeast Revitalization Group", City="Kansas City", State="KS", Type="Independent",
         Website="https://www.northeastkck.org/", Email="",
         Contact="", Phone="", Tags="Prospect",
         Notes="Neighborhood revitalization nonprofit in NE Kansas City, KS advancing food sovereignty/green space via land-reuse and garden projects with a youth Green Team. Source: https://groundworkusa.org/network/groundwork-northeast-revitalization-group/"),
]

FIELDS = ["Name", "City", "State", "Type", "Website", "Email", "Contact",
          "Phone", "Tags", "Notes"]

out = os.path.join(os.path.dirname(__file__), "new_leads_research.csv")
with open(out, "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=FIELDS)
    w.writeheader()
    for lead in LEADS:
        w.writerow(lead)

print(f"Wrote {len(LEADS)} leads to {out}")
by_metro = {}
for lead in LEADS:
    key = lead["City"] + ", " + lead["State"]
    by_metro[key] = by_metro.get(key, 0) + 1
for k in sorted(by_metro):
    print(f"  {by_metro[k]:>2}  {k}")
print("With email:", sum(1 for l in LEADS if l["Email"]))
print("With a named/contactable contact:", sum(1 for l in LEADS if l["Email"] or l["Contact"] or l["Phone"]))
