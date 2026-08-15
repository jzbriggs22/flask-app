"""
Seed data for the Gamified Birding App.
Contains bird species across rarity tiers and preset achievements.
"""

BIRDS = [
    # ===== COMMON (base XP: 10) =====
    {"common_name": "American Robin", "scientific_name": "Turdus migratorius", "rarity": "common", "family": "Turdidae", "habitat": "urban", "region": "north_america", "description": "A familiar sight on lawns across North America, known for its orange-red breast."},
    {"common_name": "House Sparrow", "scientific_name": "Passer domesticus", "rarity": "common", "family": "Passeridae", "habitat": "urban", "region": "north_america", "description": "One of the most widespread birds, found in cities and towns worldwide."},
    {"common_name": "European Starling", "scientific_name": "Sturnus vulgaris", "rarity": "common", "family": "Sturnidae", "habitat": "urban", "region": "north_america", "description": "Iridescent black birds that form spectacular murmurations."},
    {"common_name": "Mourning Dove", "scientific_name": "Zenaida macroura", "rarity": "common", "family": "Columbidae", "habitat": "urban", "region": "north_america", "description": "A graceful dove with a mournful cooing call."},
    {"common_name": "Blue Jay", "scientific_name": "Cyanocitta cristata", "rarity": "common", "family": "Corvidae", "habitat": "forest", "region": "north_america", "description": "A striking blue bird known for its intelligence and loud calls."},
    {"common_name": "Northern Cardinal", "scientific_name": "Cardinalis cardinalis", "rarity": "common", "family": "Cardinalidae", "habitat": "forest", "region": "north_america", "description": "The male's brilliant red plumage makes it one of the most recognizable birds."},
    {"common_name": "American Crow", "scientific_name": "Corvus brachyrhynchos", "rarity": "common", "family": "Corvidae", "habitat": "urban", "region": "north_america", "description": "Highly intelligent and adaptable, found across the continent."},
    {"common_name": "Black-capped Chickadee", "scientific_name": "Poecile atricapillus", "rarity": "common", "family": "Paridae", "habitat": "forest", "region": "north_america", "description": "A small, curious bird named for its distinctive call."},
    {"common_name": "Rock Pigeon", "scientific_name": "Columba livia", "rarity": "common", "family": "Columbidae", "habitat": "urban", "region": "north_america", "description": "The familiar city pigeon, descended from wild rock doves."},
    {"common_name": "Canada Goose", "scientific_name": "Branta canadensis", "rarity": "common", "family": "Anatidae", "habitat": "wetland", "region": "north_america", "description": "A large goose with a distinctive black head and white chinstrap."},
    {"common_name": "Mallard", "scientific_name": "Anas platyrhynchos", "rarity": "common", "family": "Anatidae", "habitat": "wetland", "region": "north_america", "description": "The most recognizable duck, the male has an iridescent green head."},
    {"common_name": "Song Sparrow", "scientific_name": "Melospiza melodia", "rarity": "common", "family": "Passerellidae", "habitat": "grassland", "region": "north_america", "description": "One of the most common sparrows with a beautiful, varied song."},
    {"common_name": "Red-winged Blackbird", "scientific_name": "Agelaius phoeniceus", "rarity": "common", "family": "Icteridae", "habitat": "wetland", "region": "north_america", "description": "Males display striking red and yellow shoulder patches."},
    {"common_name": "Eurasian Blue Tit", "scientific_name": "Cyanistes caeruleus", "rarity": "common", "family": "Paridae", "habitat": "forest", "region": "europe", "description": "A colorful small bird common at European garden feeders."},
    {"common_name": "Eurasian Magpie", "scientific_name": "Pica pica", "rarity": "common", "family": "Corvidae", "habitat": "urban", "region": "europe", "description": "A striking black-and-white bird famous for its intelligence."},

    # ===== UNCOMMON (base XP: 25) =====
    {"common_name": "Red-tailed Hawk", "scientific_name": "Buteo jamaicensis", "rarity": "uncommon", "family": "Accipitridae", "habitat": "grassland", "region": "north_america", "description": "North America's most common hawk, often seen soaring over open fields."},
    {"common_name": "Great Blue Heron", "scientific_name": "Ardea herodias", "rarity": "uncommon", "family": "Ardeidae", "habitat": "wetland", "region": "north_america", "description": "A tall, majestic wading bird found near waterways."},
    {"common_name": "Belted Kingfisher", "scientific_name": "Megaceryle alcyon", "rarity": "uncommon", "family": "Alcedinidae", "habitat": "wetland", "region": "north_america", "description": "A stocky bird that dives headfirst into water to catch fish."},
    {"common_name": "Eastern Bluebird", "scientific_name": "Sialia sialis", "rarity": "uncommon", "family": "Turdidae", "habitat": "grassland", "region": "north_america", "description": "A beloved songbird with vivid blue upperparts and rusty breast."},
    {"common_name": "Barn Owl", "scientific_name": "Tyto alba", "rarity": "uncommon", "family": "Tytonidae", "habitat": "grassland", "region": "north_america", "description": "A ghostly nocturnal predator with a heart-shaped face."},
    {"common_name": "Cedar Waxwing", "scientific_name": "Bombycilla cedrorum", "rarity": "uncommon", "family": "Bombycillidae", "habitat": "forest", "region": "north_america", "description": "An elegant bird with silky plumage and waxy red wingtips."},
    {"common_name": "Ruby-throated Hummingbird", "scientific_name": "Archilochus colubris", "rarity": "uncommon", "family": "Trochilidae", "habitat": "forest", "region": "north_america", "description": "The only breeding hummingbird in eastern North America."},
    {"common_name": "Osprey", "scientific_name": "Pandion haliaetus", "rarity": "uncommon", "family": "Pandionidae", "habitat": "coastal", "region": "north_america", "description": "A fish-eating raptor that plunges feet-first into water."},
    {"common_name": "Pileated Woodpecker", "scientific_name": "Dryocopus pileatus", "rarity": "uncommon", "family": "Picidae", "habitat": "forest", "region": "north_america", "description": "The largest woodpecker in North America with a flaming red crest."},
    {"common_name": "Great Horned Owl", "scientific_name": "Bubo virginianus", "rarity": "uncommon", "family": "Strigidae", "habitat": "forest", "region": "north_america", "description": "A powerful nocturnal predator with distinctive ear tufts."},
    {"common_name": "European Robin", "scientific_name": "Erithacus rubecula", "rarity": "uncommon", "family": "Muscicapidae", "habitat": "forest", "region": "europe", "description": "Britain's beloved garden bird with a bright orange-red breast."},
    {"common_name": "Common Kingfisher", "scientific_name": "Alcedo atthis", "rarity": "uncommon", "family": "Alcedinidae", "habitat": "wetland", "region": "europe", "description": "A dazzling blue-and-orange jewel of European waterways."},

    # ===== RARE (base XP: 50) =====
    {"common_name": "Bald Eagle", "scientific_name": "Haliaeetus leucocephalus", "rarity": "rare", "family": "Accipitridae", "habitat": "coastal", "region": "north_america", "description": "America's national bird, a powerful raptor with a white head."},
    {"common_name": "Snowy Owl", "scientific_name": "Bubo scandiacus", "rarity": "rare", "family": "Strigidae", "habitat": "grassland", "region": "north_america", "description": "A stunning Arctic owl that occasionally ventures south in winter."},
    {"common_name": "Painted Bunting", "scientific_name": "Passerina ciris", "rarity": "rare", "family": "Cardinalidae", "habitat": "forest", "region": "north_america", "description": "Often called the most beautiful bird in North America."},
    {"common_name": "Atlantic Puffin", "scientific_name": "Fratercula arctica", "rarity": "rare", "family": "Alcidae", "habitat": "coastal", "region": "north_america", "description": "A charismatic seabird with a colorful triangular beak."},
    {"common_name": "Roseate Spoonbill", "scientific_name": "Platalea ajaja", "rarity": "rare", "family": "Threskiornithidae", "habitat": "wetland", "region": "north_america", "description": "A striking pink wading bird with a distinctive spoon-shaped bill."},
    {"common_name": "Peregrine Falcon", "scientific_name": "Falco peregrinus", "rarity": "rare", "family": "Falconidae", "habitat": "mountain", "region": "north_america", "description": "The fastest animal on Earth, diving at over 200 mph."},
    {"common_name": "Scarlet Tanager", "scientific_name": "Piranga olivacea", "rarity": "rare", "family": "Cardinalidae", "habitat": "forest", "region": "north_america", "description": "A brilliantly red songbird that summers in eastern forests."},
    {"common_name": "Wood Duck", "scientific_name": "Aix sponsa", "rarity": "rare", "family": "Anatidae", "habitat": "wetland", "region": "north_america", "description": "Arguably the most beautifully plumaged waterfowl in the world."},
    {"common_name": "European Bee-eater", "scientific_name": "Merops apiaster", "rarity": "rare", "family": "Meropidae", "habitat": "grassland", "region": "europe", "description": "A rainbow-colored bird that catches bees and wasps in flight."},
    {"common_name": "Resplendent Quetzal", "scientific_name": "Pharomachrus mocinno", "rarity": "rare", "family": "Trogonidae", "habitat": "forest", "region": "central_america", "description": "A legendary bird sacred to ancient Mesoamerican civilizations."},

    # ===== EPIC (base XP: 100) =====
    {"common_name": "California Condor", "scientific_name": "Gymnogyps californianus", "rarity": "epic", "family": "Cathartidae", "habitat": "mountain", "region": "north_america", "description": "One of the world's rarest birds, brought back from the brink of extinction."},
    {"common_name": "Whooping Crane", "scientific_name": "Grus americana", "rarity": "epic", "family": "Gruidae", "habitat": "wetland", "region": "north_america", "description": "North America's tallest bird and one of its most endangered."},
    {"common_name": "Kirtland's Warbler", "scientific_name": "Setophaga kirtlandii", "rarity": "epic", "family": "Parulidae", "habitat": "forest", "region": "north_america", "description": "One of the rarest songbirds, nesting only in young jack pine forests."},
    {"common_name": "Ivory-billed Woodpecker", "scientific_name": "Campephilus principalis", "rarity": "epic", "family": "Picidae", "habitat": "forest", "region": "north_america", "description": "The 'Lord God Bird' -- possibly extinct, possibly still out there."},
    {"common_name": "Harpy Eagle", "scientific_name": "Harpia harpyja", "rarity": "epic", "family": "Accipitridae", "habitat": "forest", "region": "south_america", "description": "One of the most powerful eagles, ruler of tropical rainforests."},
    {"common_name": "Shoebill", "scientific_name": "Balaeniceps rex", "rarity": "epic", "family": "Balaenicipitidae", "habitat": "wetland", "region": "africa", "description": "A prehistoric-looking bird with a massive shoe-shaped bill."},
    {"common_name": "Superb Bird-of-Paradise", "scientific_name": "Lophorina superba", "rarity": "epic", "family": "Paradisaeidae", "habitat": "forest", "region": "oceania", "description": "Famous for its mind-bending courtship display transforming into an alien-like form."},

    # ===== LEGENDARY (base XP: 250) =====
    {"common_name": "Philippine Eagle", "scientific_name": "Pithecophaga jefferyi", "rarity": "legendary", "family": "Accipitridae", "habitat": "forest", "region": "asia", "description": "One of the rarest and most powerful eagles on Earth."},
    {"common_name": "Spix's Macaw", "scientific_name": "Cyanopsitta spixii", "rarity": "legendary", "family": "Psittacidae", "habitat": "forest", "region": "south_america", "description": "Extinct in the wild, the inspiration for the movie 'Rio'."},
    {"common_name": "Kakapo", "scientific_name": "Strigops habroptilus", "rarity": "legendary", "family": "Strigopidae", "habitat": "forest", "region": "oceania", "description": "The world's only flightless parrot, a nocturnal oddity from New Zealand."},
    {"common_name": "Andean Condor", "scientific_name": "Vultur gryphus", "rarity": "legendary", "family": "Cathartidae", "habitat": "mountain", "region": "south_america", "description": "One of the world's largest flying birds, soaring over the Andes."},
    {"common_name": "Steller's Sea Eagle", "scientific_name": "Haliaeetus pelagicus", "rarity": "legendary", "family": "Accipitridae", "habitat": "coastal", "region": "asia", "description": "The heaviest eagle in the world with a massive orange beak."},
]


ACHIEVEMENTS = [
    # Collection milestones
    {"name": "First Catch", "description": "Log your first bird sighting", "icon": "egg", "category": "collection", "requirement_type": "total_sightings", "requirement_value": 1},
    {"name": "Keen Observer", "description": "Log 10 bird sightings", "icon": "eyes", "category": "collection", "requirement_type": "total_sightings", "requirement_value": 10},
    {"name": "Dedicated Birder", "description": "Log 50 bird sightings", "icon": "binoculars", "category": "collection", "requirement_type": "total_sightings", "requirement_value": 50},
    {"name": "Bird Enthusiast", "description": "Log 100 bird sightings", "icon": "star", "category": "collection", "requirement_type": "total_sightings", "requirement_value": 100},
    {"name": "Master Birder", "description": "Log 500 bird sightings", "icon": "crown", "category": "collection", "requirement_type": "total_sightings", "requirement_value": 500},

    # Species milestones
    {"name": "Species Starter", "description": "Spot 5 different species", "icon": "seedling", "category": "collection", "requirement_type": "unique_species", "requirement_value": 5},
    {"name": "Growing Collection", "description": "Spot 15 different species", "icon": "herb", "category": "collection", "requirement_type": "unique_species", "requirement_value": 15},
    {"name": "Birdex Builder", "description": "Spot 30 different species", "icon": "book", "category": "collection", "requirement_type": "unique_species", "requirement_value": 30},
    {"name": "Avian Scholar", "description": "Spot 45 different species", "icon": "mortar_board", "category": "collection", "requirement_type": "unique_species", "requirement_value": 45},

    # Streak milestones
    {"name": "Getting Started", "description": "Maintain a 3-day birding streak", "icon": "fire", "category": "streak", "requirement_type": "streak", "requirement_value": 3},
    {"name": "Week Warrior", "description": "Maintain a 7-day birding streak", "icon": "fire", "category": "streak", "requirement_type": "streak", "requirement_value": 7},
    {"name": "Fortnight Flyer", "description": "Maintain a 14-day birding streak", "icon": "fire", "category": "streak", "requirement_type": "streak", "requirement_value": 14},
    {"name": "Monthly Migration", "description": "Maintain a 30-day birding streak", "icon": "fire", "category": "streak", "requirement_type": "streak", "requirement_value": 30},

    # Rarity milestones
    {"name": "Uncommon Find", "description": "Spot your first uncommon bird", "icon": "mag", "category": "mastery", "requirement_type": "rarity_uncommon", "requirement_value": 1},
    {"name": "Rare Discovery", "description": "Spot your first rare bird", "icon": "gem", "category": "mastery", "requirement_type": "rarity_rare", "requirement_value": 1},
    {"name": "Epic Encounter", "description": "Spot your first epic bird", "icon": "dizzy", "category": "mastery", "requirement_type": "rarity_epic", "requirement_value": 1},
    {"name": "Legendary Moment", "description": "Spot your first legendary bird", "icon": "trophy", "category": "mastery", "requirement_type": "rarity_legendary", "requirement_value": 1},

    # Level milestones
    {"name": "Fledgling", "description": "Reach level 5", "icon": "bird", "category": "mastery", "requirement_type": "level", "requirement_value": 5},
    {"name": "Soaring High", "description": "Reach level 10", "icon": "eagle", "category": "mastery", "requirement_type": "level", "requirement_value": 10},
    {"name": "Sky Master", "description": "Reach level 15", "icon": "rocket", "category": "mastery", "requirement_type": "level", "requirement_value": 15},
    {"name": "Apex Birder", "description": "Reach level 20", "icon": "100", "category": "mastery", "requirement_type": "level", "requirement_value": 20},
]
