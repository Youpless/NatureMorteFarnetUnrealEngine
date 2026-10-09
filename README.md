# Vanité de Franz : nature morte, version Unreal Engine

Devoir « matières, lumières, post-process », dans l'esthétique du PFE *La Bibliothèque infinie : A Matter of Time*.
Version Unity du même projet : **[lien vers le dépôt Unity]**

![Capture Unreal](Captures/nature_morte_unreal.png)

## Intention

<!-- À écrire avec tes mots : inspiration, ce que raconte l'image, choix de lumière, de matières, de post-process,
     lien avec le PFE. La planche d'intention peut être ajoutée dans Docs/ et affichée ici :
     ![Planche d'intention](Docs/planche_intention.jpg) -->

## Ouvrir le projet

- **Unreal Engine 5** (5.4 à 5.6), Lumen pour l'éclairage indirect et les reflets.
- Ouvrir le niveau `Content/NatureMorte/Maps/NatureMorte`.
- Sélectionner `NM_Camera`, clic droit, *Pilot*, puis touche **G** pour la vue de jeu. Capture : `r.HighResScreenshotDelay 64`, puis `HighResShot 1920x1080` dans la console.
- Pour régler à nouveau la scène à partir des fichiers source : *Tools > Execute Python Script…* > `Content/Python/nature_morte_unreal.py` (plugin *Python Editor Script Plugin* requis).

## Méthode

Unreal et Unity lisent les mêmes données : la géométrie `SourceArt/NatureMorte/nature_morte.gltf` et les paramètres `SourceArt/NatureMorte/parametres_rendu.json`, qui décrivent les matières, les lumières en unités physiques, l'exposition, la caméra et le post-process. Le script `Content/Python/nature_morte_unreal.py` crée les matériaux et règle la scène à partir de ces fichiers. Le script C# de la version Unity fait de même. Les valeurs sont donc les mêmes dans les deux moteurs, et seules les conversions propres à chaque moteur diffèrent.

## Matières

Trois matériaux maîtres (`Content/NatureMorte/Materiaux/Maitres`) et une instance par matière (`MI_…`) :

| Catégorie demandée | Dans la scène | Réglage Unreal |
|---|---|---|
| Opaque non métallique | cuirs, bois, pierre, cire, pages, sable, encre | `M_NM_Standard`, *Opaque*, métal 0 (ORM bleu), rugosité de 0,06 (encre) à 1, cartes de normales |
| Opaque métallique | laiton (lanterne, bougeoirs, montre, encrier), dorure, fer | `M_NM_Standard`, métal 1 (ORM bleu), rugosité dans ORM vert |
| Transparent | verre du sablier, de la lanterne, des lunettes, de l'encrier, de la montre | `M_NM_Verre` : *Translucent*, éclairage *Surface ForwardShading*, opacité 0,14 qui monte à 0,55 sur les bords (Fresnel), sans ombre portée |
| Masqué (bonus) | dentelle du rideau, plume, feuillets, masque de cuir, parchemin énochien | instance de `M_NM_Standard` en *Blend Mode Masked*, seuil 0,5, *Two Sided* |
| Additif (en plus) | flammes, rayon de lumière, poussière | `M_NM_Additif` : *Additive*, *Unlit*, émission en nits |

## Lumières

Unités physiques, exposition manuelle **EV100 = 1** (*Metering Mode Manual*, *Apply Physical Camera Exposure* décoché, *Exposure Compensation* −1).

| Lumière | Type | Intensité | Couleur | Ombres |
|---|---|---|---|---|
| Lumière froide de la fenêtre | directionnelle, 30° au-dessus de l'horizon | 8 lux | bleutée, environ 8 300 K | nettes (angle 1°) |
| Lanterne | ponctuelle | 3 cd | ambre, environ 3 600 K | douces (rayon 1,2 cm) |
| Bougies (2) | ponctuelles | 1,4 cd | orangée, environ 3 100 K | douces (rayon 0,8 cm) |
| Sceau énochien | ponctuelle | 0,08 cd | bleue | non |

S'y ajoutent Lumen (éclairage indirect et reflets) et la capture de reflets `NM_Reflets` au-dessus du bureau.

## Post-process

Volume `NM_PostProcess` (non borné, priorité 10) et brouillard `NM_Brouillard` :

| Effet | Valeur | Rôle |
|---|---|---|
| Exposition manuelle | EV100 = 1 | même exposition que la version Unity |
| Tone mapping | filmique (ACES) | flammes adoucies, ombres profondes |
| Bloom | 0,55 | halo autour des flammes et du sceau |
| Profondeur de champ | caméra cinéma 26,38 mm, f/2, mise au point 1,66 m | le livre ouvert net, l'abîme flou |
| Vignette | 0,45 | ramener le regard vers le centre éclairé |
| Grain | 0,08 | texture de pellicule ancienne |
| Aberration chromatique | 0,25 | optique imparfaite, très légère |
| Saturation et contraste | 0,94 et 1,05 | tonalité de gravure |
| Brouillard | homogène, densité 0,946 (22 m), chute de hauteur 0,001, couleur bleutée | profondeur de l'abîme |
| Occlusion ambiante | 0,6, rayon 60 cm | ancrer les objets sur le bureau |
| Flou de mouvement | 0 | image fixe |

## Arborescence

```
Content/
├── NatureMorte/
│   ├── Maps/NatureMorte          niveau
│   ├── Import/                   maillages importés du glTF
│   ├── Materiaux/                instances MI_… et matériaux maîtres
│   └── Textures/
└── Python/nature_morte_unreal.py réglage de la scène
SourceArt/NatureMorte/            glTF, paramètres partagés avec Unity, textures
Captures/                         captures 1920 x 1080
```
