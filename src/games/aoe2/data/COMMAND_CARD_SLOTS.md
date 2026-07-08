# Command-card & build-menu slot map (command id → grid slot)

Pairs each hotkey **command id** to its **grid slot** (0–14; `row = slot//5`, `col = slot%5`,
top-left = 0). Readable companion to two machine files:
- **`positions.json`** — command-card slots (train/research + command actions).
- **`build_menu_positions.json`** — villager **build-submenu** slots (a *separate* grid).

Multiple commands can share a slot — civ-replacement units/buildings occupy the same slot
(e.g. Settlement/Mill, Feitoria/Caravanserai/Port), and context-shared action buttons too.

---

# Command cards
Sources: unit/tech buttons from the `.dat` (`button_id - 1`); command actions from
`buttons.json` `sequence_id`.

## All production buildings (gather point)

| Slot | Row,Col | ID | Command |
|-----:|:-------:|----|---------|
| 4 | 0,4 | `19002` | Set Gather Point |
| 4 | 0,4 | `19121` | Remove Gather Point |

## Archery Range

| Slot | Row,Col | ID | Command |
|-----:|:-------:|----|---------|
| 0 | 0,0 | `19038` | Archer-line |
| 1 | 0,1 | `19043` | Skirmisher |
| 2 | 0,2 | `19040` | Cavalry Archer |
| 2 | 0,2 | `19145` | Elephant Archer |
| 3 | 0,3 | `19041` | Hand Cannoneer |
| 3 | 0,3 | `19126` | Slinger, Grenadier |
| 5 | 1,0 | `19458` | Tech: Crossbowman, Arbalester |
| 6 | 1,1 | `19459` | Tech: Elite, Imperial Skirmisher |
| 7 | 1,2 | `19149` | Tech: Elite Bolas Rider |
| 7 | 1,2 | `19460` | Tech: Heavy Cavalry Archer, Elite Elephant Archer |
| 8 | 1,3 | `19032` | Genitour |
| 10 | 2,0 | `19461` | Tech: Thumb Ring |
| 12 | 2,2 | `19462` | Tech: Parthian Tactics |
| 13 | 2,3 | `19463` | Tech: Elite Genitour |

## Barracks

| Slot | Row,Col | ID | Command |
|-----:|:-------:|----|---------|
| 0 | 0,0 | `19035` | Militia-line |
| 1 | 0,1 | `19034` | Spearman-line |
| 2 | 0,2 | `19073` | Condottiero |
| 3 | 0,3 | `19070` | Eagle Warrior, Fire Lancer |
| 3 | 0,3 | `19141` | Flemish Militia |
| 3 | 0,3 | `419001` | Hoplite |
| 3 | 0,3 | `419216` | Phalangite |
| 5 | 1,0 | `19451` | Tech: Swordsmen, Champi Upgrades |
| 6 | 1,1 | `19452` | Tech: Pikeman, Halberdier |
| 8 | 1,3 | `19453` | Tech: Eagle Warrior, Fire Lancer, Hoplite |
| 8 | 1,3 | `19166` | Tech: Elite Ibirapema, Temple Guard |
| 8 | 1,3 | `419217` | Tech: Elite Phalangite |
| 10 | 2,0 | `19454` | Tech: Gambesons |
| 10 | 2,0 | `419038` | Tech: Battle Drills |
| 11 | 2,1 | `19455` | Tech: Squires |
| 12 | 2,2 | `19456` | Tech: Arson |

## Castle

| Slot | Row,Col | ID | Command |
|-----:|:-------:|----|---------|
| 2 | 0,2 | `19069` | Petard |
| 10 | 2,0 | `19083` | Tech: Hoardings |
| 11 | 2,1 | `19084` | Tech: Sappers |
| 12 | 2,2 | `19085` | Tech: Conscription |
| 13 | 2,3 | `19086` | Tech: Spies/Treason |

## Dock

| Slot | Row,Col | ID | Command |
|-----:|:-------:|----|---------|
| 0 | 0,0 | `19045` | Fishing Ship |
| 1 | 0,1 | `19059` | Galley, Galleon |
| 2 | 0,2 | `19355` | Hulk |
| 3 | 0,3 | `19279` | Fire Ship |
| 5 | 1,0 | `19284` | Transport Ship |
| 6 | 1,1 | `19044` | Trade Cog |
| 7 | 1,2 | `19280` | Demolition Ship |
| 8 | 1,3 | `19055` | Cannon Galleon |
| 8 | 1,3 | `19154` | Dromon, Lou Chuan |
| 10 | 2,0 | `19341` | Tech: Fishing Lines, Gillnets |
| 12 | 2,2 | `19345` | Tech: Heavy Demolition Ship |
| 13 | 2,3 | `19347` | Tech: Elite Cannon Galleon |
| 14 | 2,4 | `19217` | More Items |
| 14 | 2,4 | `19358` | Thirisadai |
| 14 | 2,4 | `19743` | Go Back to Work (Fortified Church, Dock) |

## Donjon

| Slot | Row,Col | ID | Command |
|-----:|:-------:|----|---------|
| 1 | 0,1 | `19167` | Spearman-line |

## Garrisons / Transports

| Slot | Row,Col | ID | Command |
|-----:|:-------:|----|---------|
| 9 | 1,4 | `20208` | Ungarrison |

## Market

| Slot | Row,Col | ID | Command |
|-----:|:-------:|----|---------|
| 1 | 0,1 | `19348` | Tech: Caravan |
| 2 | 0,2 | `19349` | Tech: Coinage, Banking |
| 3 | 0,3 | `19450` | Tech: Guilds |

## Monastery

| Slot | Row,Col | ID | Command |
|-----:|:-------:|----|---------|
| 0 | 0,0 | `19051` | Monk |
| 1 | 0,1 | `19478` | Tech: Redemption |
| 2 | 0,2 | `19479` | Tech: Atonement |
| 3 | 0,3 | `19480` | Tech: Fervor |
| 5 | 1,0 | `19481` | Tech: Sanctity |
| 6 | 1,1 | `19482` | Tech: Devotion, Faith |
| 7 | 1,2 | `19483` | Tech: Illumination |
| 8 | 1,3 | `19484` | Tech: Block Printing |
| 10 | 2,0 | `19485` | Tech: Heresy |
| 11 | 2,1 | `19486` | Tech: Theocracy |
| 12 | 2,2 | `19487` | Tech: Herbal Medicine |
| 13 | 2,3 | `19071` | Missionary, Religious Infantry |

## Outpost

| Slot | Row,Col | ID | Command |
|-----:|:-------:|----|---------|
| 0 | 0,0 | `419137` | Tech: Fortified Outpost |

## Port

| Slot | Row,Col | ID | Command |
|-----:|:-------:|----|---------|
| 0 | 0,0 | `419011` | Fishing Ship |
| 2 | 0,2 | `419012` | Merchant Ship |
| 3 | 0,3 | `419014` | Lembos |
| 5 | 1,0 | `419016` | Tech: Scoop Nets |
| 6 | 1,1 | `419017` | Tech: Drums |
| 7 | 1,2 | `419018` | Tech: Shipwright |

## Shipyard

| Slot | Row,Col | ID | Command |
|-----:|:-------:|----|---------|
| 0 | 0,0 | `419019` | Monoreme |
| 2 | 0,2 | `419021` | Incendiary Raft |
| 3 | 0,3 | `419023` | Catapult Ship |
| 5 | 1,0 | `419025` | Tech: Bireme, Trireme |
| 8 | 1,3 | `419029` | Tech: Onager Ship |
| 10 | 2,0 | `419024` | Leviathan |
| 11 | 2,1 | `419030` | Tech: Hypozomata |

## Siege Workshop

| Slot | Row,Col | ID | Command |
|-----:|:-------:|----|---------|
| 0 | 0,0 | `19056` | Battering Ram |
| 0 | 0,0 | `19146` | Armored Elephant |
| 1 | 0,1 | `19285` | Mangonel, Onager, Rocket Cart |
| 2 | 0,2 | `19049` | Scorpion, War Chariot |
| 3 | 0,3 | `19047` | Bombard Cannon, Traction Trebuchet |
| 3 | 0,3 | `19134` | Flaming Camel, Mounted Trebuchet |
| 5 | 1,0 | `19150` | Tech: Siege Elephant |
| 5 | 1,0 | `19475` | Tech: Capped, Siege Ram |
| 6 | 1,1 | `19476` | Tech: (Siege) Onager, Heavy Rocket Cart |
| 7 | 1,2 | `19477` | Tech: Heavy Scorpion |
| 8 | 1,3 | `19142` | Tech: Houfnice |
| 13 | 2,3 | `19048` | Siege Tower |

## Stable

| Slot | Row,Col | ID | Command |
|-----:|:-------:|----|---------|
| 0 | 0,0 | `19060` | Scout Cavalry, Hussar |
| 0 | 0,0 | `19143` | Xolotl Warrior |
| 1 | 0,1 | `19030` | Knight-line, Hei Guang Cavalry |
| 1 | 0,1 | `19147` | Shrivamsha Rider |
| 2 | 0,2 | `19031` | Camel Rider |
| 3 | 0,3 | `19033` | Battle Elephant |
| 3 | 0,3 | `19124` | Tarkan |
| 3 | 0,3 | `19127` | Steppe Lancer |
| 3 | 0,3 | `419218` | Sannāhya |
| 5 | 1,0 | `19464` | Tech: Light Cavalry, Hussar |
| 6 | 1,1 | `19151` | Tech: Elite Shrivamsha Rider |
| 6 | 1,1 | `19465` | Tech: Knight-line, Hei Guang Cavalry |
| 7 | 1,2 | `19466` | Tech: Heavy, Imperial Camel Rider |
| 8 | 1,3 | `19152` | Tech: Elite Battle Elephant |
| 8 | 1,3 | `19467` | Tech: Elite Steppe Lancer |
| 8 | 1,3 | `419004` | Tech: Elite War Chariot |
| 8 | 1,3 | `419219` | Tech: Elite Sannāhya |
| 10 | 2,0 | `19468` | Tech: Bloodlines |
| 11 | 2,1 | `19469` | Tech: Husbandry |

## Town Center

| Slot | Row,Col | ID | Command |
|-----:|:-------:|----|---------|
| 1 | 0,1 | `419033` | Polemarch |
| 1 | 0,1 | `419042` | Tech: Economic Town Center |
| 1 | 0,1 | `419045` | Tech: Economic Policy |
| 2 | 0,2 | `419043` | Tech: Military Town Center |
| 2 | 0,2 | `419046` | Tech: Naval Policy |
| 2 | 0,2 | `419050` | Tech: Ephorate |
| 3 | 0,3 | `419044` | Tech: Defensive Town Center |
| 3 | 0,3 | `419047` | Tech: Military Policy |
| 3 | 0,3 | `419051` | Tech: Morai |
| 5 | 1,0 | `19333` | Tech: Loom |
| 6 | 1,1 | `19334` | Tech: Wheelbarrow, Hand Cart |
| 7 | 1,2 | `19335` | Tech: Town Watch, Town Patrol |
| 8 | 1,3 | `19324` | Go Back to Work |
| 11 | 2,1 | `419048` | Tech: Skeuophoroi, Hippagretai |
| 13 | 2,3 | `400018` | All Back to Work |
| 14 | 2,4 | `19319` | Ring Town Bell |

## University

| Slot | Row,Col | ID | Command |
|-----:|:-------:|----|---------|
| 0 | 0,0 | `19488` | Tech: Masonry, Architecture |
| 1 | 0,1 | `19489` | Tech: Treadmill Crane |
| 2 | 0,2 | `19490` | Tech: Heated Shot |
| 3 | 0,3 | `19491` | Tech: Ballistics |
| 4 | 0,4 | `19492` | Tech: Chemistry, Bombard Tower |
| 5 | 1,0 | `19493` | Tech: Siege Engineers |
| 6 | 1,1 | `19495` | Tech: Murder Holes |
| 7 | 1,2 | `19497` | Tech: Fortified Wall |
| 9 | 1,4 | `19494` | Tech: Arrowslits |
| 10 | 2,0 | `19342` | Tech: Careening, Dry Dock |
| 11 | 2,1 | `19356` | Tech: Clinker Construction, Carvel Hull |
| 12 | 2,2 | `19343` | Tech: Shipwright |
| 13 | 2,3 | `19357` | Tech: Siphons, Incendiaries |

---

# Villager build submenus (a separate grid from the command cards)
Source: each building’s `.dat` `creatable.train_locations` → the "Builder" unit (118)
`button_id - 1`. The page (Economic / Military) comes from the `B:eco` / `B:mil` context.

## Build Economic Buildings  &nbsp;`(B:eco)`

| Slot | Row,Col | ID | Command |
|-----:|:-------:|----|---------|
| 0 | 0,0 | `19213` | House |
| 1 | 0,1 | `19163` | Settlement |
| 1 | 0,1 | `19236` | Mill |
| 2 | 0,2 | `19288` | Mining Camp |
| 3 | 0,3 | `19158` | Mule Cart |
| 3 | 0,3 | `19283` | Lumber Camp |
| 4 | 0,4 | `19067` | Dock |
| 5 | 1,0 | `19200` | Farm, Pasture |
| 6 | 1,1 | `19063` | Blacksmith |
| 7 | 1,2 | `19237` | Market |
| 8 | 1,3 | `19065` | Monastery |
| 9 | 1,4 | `19208` | University |
| 10 | 2,0 | `19238` | Town Center |
| 11 | 2,1 | `19209` | Wonder |
| 12 | 2,2 | `19075` | Feitoria |
| 12 | 2,2 | `19148` | Caravanserai |
| 12 | 2,2 | `419007` | Port |

## Build Military Buildings  &nbsp;`(B:mil)`

| Slot | Row,Col | ID | Command |
|-----:|:-------:|----|---------|
| 0 | 0,0 | `19064` | Barracks |
| 1 | 0,1 | `19062` | Archery Range |
| 2 | 0,2 | `19206` | Stable |
| 3 | 0,3 | `19205` | Siege Workshop |
| 4 | 0,4 | `19138` | Donjon |
| 4 | 0,4 | `19329` | Krepost |
| 4 | 0,4 | `419008` | Shipyard |
| 5 | 1,0 | `19203` | Outpost |
| 6 | 1,1 | `19210` | Palisade Wall |
| 7 | 1,2 | `19211` | Stone Wall |
| 9 | 1,4 | `19204` | Bombard Tower |
| 10 | 2,0 | `19264` | Gate |
| 11 | 2,1 | `19212` | Palisade Gate |
| 12 | 2,2 | `19066` | Castle |

---

# Command-card commands still with no slot
(gate + fish-trap actions, line-upgrade `Tech: X-line` techs, generic unique-unit slots)

- **Archery Range:** `419141` Cycle Recruitment Doctrine (Archery Range)
- **Barracks:** `19125` Infantry Unique Units, `419140` Cycle Recruitment Doctrine (Barracks)
- **Blacksmith:** `19470` Tech: Melee Attack Upgrades, `19471` Tech: Infantry Armor Upgrades, `19472` Tech: Cavalry Armor Upgrades, `19473` Tech: Arrow Attack Upgrades, `19474` Tech: Archer Armor Upgrades
- **Castle:** `19080` Tech: Elite Unique Unit, `19081` Tech: Unique Castle Technology, `19082` Tech: Unique Imperial Technology, `19130` Elite Kipchak (Mercenary), `19321` Trebuchet, Heroes, `19322` Unique Unit
- **Dock:** `19053` Unique Warships, `19101` Toggle Automatic Fish Trap Rebuilding, `19123` Rebuild Fish Trap, `19344` Tech: War Galley, Galleon, `19457` Tech: Elite Unique Ship
- **Donjon:** `19187` Unique Unit
- **Fort:** `19181` Tech: Conscription, `19182` Tech: Spies/Treason, `19185` Elite Kipchak (Mercenary), `419005` Tech: First Unique Classical Technology, `419006` Tech: First Unique Imperial Technology, `419058` Tech: Second Unique Classical Technology, `419059` Tech: Second Unique Imperial Technology, `419138` Tech: Defensive Emplacement, `419139` Tech: Offensive Emplacement
- **Lumber Camp:** `19340` Tech: Wood Upgrades
- **Market:** `19102` Sell 100 Food, `19103` Sell 100 Wood, `19104` Sell 100 Stone, `19111` Buy 100 Food, `19112` Buy 100 Wood, `19113` Buy 100 Stone, `19286` Trade Cart
- **Mill:** `19074` Reseed Farm, `19100` Toggle Automatic Farm Reseeding, `19337` Tech: Farm, Pasture Upgrades
- **Mining Camp:** `19338` Tech: Gold Upgrades, `19339` Tech: Stone Upgrades
- **Mule Cart:** `19170` Tech: Gold Upgrades, `19172` Tech: Stone Upgrades, `19174` Tech: Wood Upgrades
- **Port:** `19183` Toggle Automatic Fish Trap Rebuilding, `19184` Rebuild Fish Trap, `419013` Transport Ship, `419015` Tech: (War, Heavy, Elite) Lembos, `419057` Toggle Trading Ratio
- **Settlement:** `19168` Spearman-line, `19169` Tech: Farm, Pasture Upgrades, `19171` Tech: Gold Upgrades, `19173` Tech: Stone Upgrades, `19175` Tech: Wood Upgrades, `19179` Skirmisher, `19188` Tech: Pikeman, Halberdier, `19189` Tech: Elite, Imperial Skirmisher
- **Shipyard:** `419020` Galley, `419026` Tech: (Heavy, Elite) Galley, `419027` Tech: (Heavy) Incendiary Ship
- **Siege Workshop:** _(all mapped)_
- **Stable:** `419003` War Chariot, `419142` Cycle Recruitment Doctrine (Stable)
- **Town Center:** `19054` Villager, `19336` Tech: Age Up
- **University:** `19496` Tech: Tower Upgrades
- **gate:** `19122` Lock/Unlock Gate, `19331` Rotate Gate Clockwise, `19332` Rotate Gate Counterclockwise
