Lets frame the whole project in a larger context now. we will define this as a full pipeline that allows streamlining game design using godot as the engine, and a structure of defined characteristics to frame how a variety of different media can be ingested to create or influence a structured set of assets. we will plan the architecture of this project in a larger sense, but the high-level brief looks like this.

We will be building the overarching structure first, the establishing indiivdual modules, but the overall goal is fairly ambitiuous; create a structure of asset creation and management on top of godot that allows for game-creation of a fairly wide array of game types, using various different AI generative and extracting capabilities to streamline the process as far as can be done. We will couple that with more generic capabilities of digital infrastructure extraction for the purposes of representation, particularly building around the IFC standard, so that the various ingestion and modification pipeline can be used outside of a video-game design context (generating, ingestion plans, images, or textual description of a building should be fully integrated with the IFC standard of BIM so that any module with those intentions can be ported out of this project and integrated as individual compo)

Before we go into brainstorming mode to establish current possible weak spot, inflection points and architecture design, we need to keep a few things in mind. No current components need to be designed around, we can consider everything done so far as purely exploratory, and if useful we can re-purpose and integrate into our larger design, but it definitely does not have to be so. 

Lets also see if we can take the engine developped for our roman steampuk game (entropy) and what can be re-used or re-tooled here. (codebase is located here: https://github.com/tavernierdetk/EntropySnapShot.git) and the pixel-art asset creator (https://github.com/tavernierdetk/PixelAssetCreator.git): 

Lets look at using google maps/open maps api to associate GPS coordinates provided by the drone to real-life data, and whether a data-source merge engine can be used. 

Lets draw a list of possible end-statuses for this project, what the value added of each is, and what is necessary to get there. Candidates:
    -Full conversion from open map data, skip drone footage altogether?
    -multi-layered level of details, including inside of buildings, and how can reconciliation be done, what level of terrain mapping can be done purely from publicaly available data, and what needs bonification

Getting to a full character creation feature with claude, using auto-generated assets

Modular engine, where terrain ingestion to level design is a separate pipeline including styling, with clrearly defined boundaries,  character/asset creation is another one, and game mechanics is a third, all with appropriately designed sub-components. 

Separation of infrastructure level assets, and scenery/character-level assets. 

Could there be a BIM backbone to the asset creation, using IFC backbone?
IFC level could be the determining factor of what belongs to which.


Top-level characteristic:
    Visual identity:
        -resolution?
        -color palettes (number, variety, composition)
        -anything that can be applied through general masks. (cell-shading v. traditionnal polygon? lets get a list of 3-d styles that could be adjustable)


Level Design
    Lets consider level design as a funnel-type pipeline, with procedurally generated at it's wider access point, and manual edition at its end, with various methods of entering different parts of the pipeline. for instance, there should be a standardized generation spec-sheet, interacting with the visual identity components at the top level, the game scope at the mechanics level, along with the movement characteristics. 

    intakes:  
        -Procedurally generated, manually enriched, or multi-level of procedural, LLM generation of detail characteristics, with gradually more granular personnalization possible.
        -Open maps data
        -Drone footage

        -Textual level description
        -Non-standard/representative images.


    transformation capabilities:
        -Post apocalyptic RPG that transforms existing landscape into post apoc versions of it.

        

Asset creations
    Asset families (asset-type taxonomy)
    Textures and building blocks strategy

    Creatures:
        Creature level characteristics:
            -Size
            -Color identity
            -Detail
            -Statistics (interface with game mechanics)

        Humanoids
            -head, eyebrows, etc...
            -limb proportions, posture, etc...


        Quadrupeds
        Custom form factor


    Items

    Furniture


    Asset to mechanic mapping infrastructure

Game mechanics
        -Story design
            -standardized story tree, with decision branches/nodes?
        -Game scope (number of levels, respective sizes, types of interaction)
        -Core mechanics
            -RPG family
            -character interaction with environment
            -Movement possibilities (ground-only, bounded flight, platform, etc...)
        -User interfaces
            -Modal, hud, (interface with visual identity)

        

        


