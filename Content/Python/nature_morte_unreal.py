# -*- coding: utf-8 -*-
"""Nature morte « Vanité de Franz » — La Bibliothèque infinie — Unreal Engine 5 (5.4 à 5.6 ; 5.3 non vérifiée).

Règle la scène importée à partir des mêmes données que la version Unity :
  SourceArt/NatureMorte/nature_morte.gltf      géométrie, lumières, caméra (importé dans le niveau)
  SourceArt/NatureMorte/parametres_rendu.json  matériaux, lumières, exposition, post-process
  SourceArt/NatureMorte/textures/              textures

Utilisation (voir le README) :
  1. Nouveau niveau vide, enregistré dans /Game/NatureMorte/Maps.
  2. File > Import Into Level... > SourceArt/NatureMorte/nature_morte.gltf (le script tente aussi cet import tout seul).
  3. Tools > Execute Python Script... > Content/Python/nature_morte_unreal.py
Le script peut être relancé : il met à jour les matériaux et réglages existants au lieu de les dupliquer.
"""
import json
import math
import os

import unreal

# ------------------------------------------------------------------ réglages
DOSSIER_SOURCE = None          # chemin absolu ; None = <Projet>/SourceArt/NatureMorte
DEST = "/Game/NatureMorte"
DEST_TEX = DEST + "/Textures"
DEST_MAT = DEST + "/Materiaux"
DEST_MAITRES = DEST_MAT + "/Maitres"
DEST_IMPORT = DEST + "/Import"
CAPTURE_AUTO = True            # capture 1920 x 1080 depuis la caméra à la fin du script
RESOLUTION_CAPTURE = (1920, 1080)
PREFIXE = "NM_"                # étiquette des acteurs créés par le script

MEL = unreal.MaterialEditingLibrary
EAL = unreal.EditorAssetLibrary
AVERTISSEMENTS = []


def info(msg):
    unreal.log("[Nature morte] " + msg)


def avert(msg):
    AVERTISSEMENTS.append(msg)
    unreal.log_warning("[Nature morte] " + msg)


def lc(c, a=1.0):
    """Couleur linéaire (liste 3 ou 4 valeurs) vers unreal.LinearColor. Attention : l'alpha par défaut d'Unreal vaut 0."""
    return unreal.LinearColor(r=float(c[0]), g=float(c[1]), b=float(c[2]), a=float(c[3]) if len(c) > 3 else float(a))


def acteurs():
    return unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors()


def acteur_par_etiquette(etiquette):
    for a in acteurs():
        try:
            if a.get_actor_label() == etiquette:
                return a
        except Exception:
            pass
    return None


def creer_acteur(classe, etiquette, position=None):
    a = acteur_par_etiquette(etiquette)
    if a is not None:
        return a
    eas = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    a = eas.spawn_actor_from_class(classe, position or unreal.Vector(0.0, 0.0, 0.0))
    a.set_actor_label(etiquette)
    return a


# ------------------------------------------------------------------ fichiers source
def trouver_source():
    candidats = []
    if DOSSIER_SOURCE:
        candidats.append(DOSSIER_SOURCE)
    projet = unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir())
    candidats += [os.path.join(projet, "SourceArt", "NatureMorte"), os.path.join(projet, "NatureMorte_Source"),
                  os.path.join(projet, "SourceArt", "NatureMorte_Source")]
    for c in candidats:
        if os.path.isfile(os.path.join(c, "parametres_rendu.json")) and os.path.isfile(os.path.join(c, "nature_morte.gltf")):
            return os.path.normpath(c)
    # Copie au mauvais endroit (par exemple dans Content) : on cherche dans tout le projet, hors des dossiers générés.
    exclus = {"Saved", "Intermediate", "DerivedDataCache", "Binaries", ".git", ".vs", ".idea"}
    for racine, dossiers, fichiers in os.walk(projet):
        dossiers[:] = [d for d in dossiers if d not in exclus]
        if "parametres_rendu.json" in fichiers and "nature_morte.gltf" in fichiers:
            avert("Fichiers source trouvés dans " + os.path.normpath(racine) + ". Leur place est "
                  + os.path.join(projet, "SourceArt", "NatureMorte") + " : à côté du .uproject, hors de Content "
                  + "(dans Content, Unreal peut importer ces fichiers en double). Déplace le dossier quand tu peux.")
            return os.path.normpath(racine)
    raise RuntimeError("Dossier source introuvable. Copie le dossier SourceArt de l'archive à la racine du projet, à côté du "
                       ".uproject, pour obtenir " + os.path.join(projet, "SourceArt", "NatureMorte")
                       + ", ou renseigne DOSSIER_SOURCE en haut du script.")


# ------------------------------------------------------------------ contenu importé
def cles_materiaux(prm):
    return list(prm["materiaux"].keys())


def meilleure_cle(candidats, cles):
    """Associe un emplacement de matériau importé à nos noms : la clé la plus longue contenue dans un des noms gagne
    (ainsi « M_Flamme_Coeur » ne devient pas « M_Flamme »)."""
    meilleure = None
    for k in cles:
        kl = k.lower()
        for c in candidats:
            if c and kl in c.lower():
                if meilleure is None or len(k) > len(meilleure):
                    meilleure = k
    return meilleure


def noms_emplacements(comp):
    sm = comp.get_editor_property("static_mesh")
    noms = []
    if sm is None:
        return noms
    try:
        emplacements = sm.get_editor_property("static_materials")
    except Exception:
        emplacements = []
    for i in range(comp.get_num_materials()):
        cands = []
        if i < len(emplacements):
            try:
                cands.append(str(emplacements[i].get_editor_property("material_slot_name")))
                mi = emplacements[i].get_editor_property("material_interface")
                if mi is not None:
                    cands.append(mi.get_name())
            except Exception:
                pass
        cur = comp.get_material(i)
        if cur is not None:
            cands.append(cur.get_name())
        noms.append(cands)
    return noms


def composants_scene(prm):
    """Composants de maillage dont au moins un emplacement correspond à un de nos matériaux."""
    cles = cles_materiaux(prm)
    res = []
    for a in acteurs():
        try:
            comps = a.get_components_by_class(unreal.StaticMeshComponent)
        except Exception:
            continue
        for c in comps:
            if c.get_editor_property("static_mesh") is None:
                continue
            if any(meilleure_cle(cands, cles) for cands in noms_emplacements(c)):
                res.append((a, c))
    return res


def verifier_niveau(composants):
    """Signale ce qui fausserait l'image : scène importée deux fois, ciel, autre volume de post-process ou autre brouillard."""
    vus = {}
    for a, c in composants:
        sm = c.get_editor_property("static_mesh")
        nom = sm.get_name() if sm is not None else ""
        vus[nom] = vus.get(nom, 0) + 1
    doubles = sorted(n for n, k in vus.items() if k > 1)
    if doubles:
        avert("Maillages présents plusieurs fois dans le niveau (scène importée deux fois ?) : " + ", ".join(doubles[:6])
              + ". Supprime les acteurs en double.")
    genants = []
    for a in acteurs():
        try:
            lab = a.get_actor_label()
            if isinstance(a, (unreal.SkyLight, unreal.SkyAtmosphere, unreal.VolumetricCloud)):
                genants.append(lab)
            elif isinstance(a, unreal.PostProcessVolume) and lab != PREFIXE + "PostProcess":
                genants.append(lab)
            elif isinstance(a, unreal.ExponentialHeightFog) and lab != PREFIXE + "Brouillard":
                genants.append(lab)
        except Exception:
            pass
    if genants:
        avert("Acteurs qui faussent la lumière ou l'exposition (niveau Basic ?) : " + ", ".join(genants[:8]) + ". Supprime-les.")


def importer_scene(source):
    """Import du glTF dans le niveau par Interchange (équivalent de File > Import Into Level).
    Renvoie "deja" si des assets importés existent déjà (pas de nouvel import, pour éviter les doublons), True si l'import
    a été lancé, False en cas d'échec."""
    try:
        if EAL.does_directory_exist(DEST_IMPORT) and EAL.list_assets(DEST_IMPORT, recursive=True, include_folder=False):
            avert("Des maillages importés existent déjà dans %s : pas de nouvel import, pour éviter les doublons." % DEST_IMPORT)
            return "deja"
    except Exception:
        pass
    gltf = os.path.join(source, "nature_morte.gltf")
    try:
        mgr = unreal.InterchangeManager.get_interchange_manager_scripted()
        donnees = unreal.InterchangeManager.create_source_data(gltf)
        params = unreal.ImportAssetParameters()
        params.set_editor_property("is_automated", True)
        ok = mgr.import_scene(DEST_IMPORT, donnees, params)
        try:
            mgr.wait_until_all_tasks_done(False)   # 5.6 et plus
        except Exception:
            pass
        return bool(ok)
    except Exception as e:
        avert("Import automatique impossible (" + str(e) + "). Fais File > Import Into Level puis relance le script.")
        return False


# ------------------------------------------------------------------ textures
def importer_textures(source, prm):
    besoins = {}
    for m in prm["materiaux"].values():
        if m.get("texture_couleur"):
            besoins[m["texture_couleur"]] = "couleur"
        if m.get("texture_normale"):
            besoins[m["texture_normale"]] = "normale"
        if m.get("texture_orm_unreal"):
            besoins[m["texture_orm_unreal"]] = "lineaire"
        em = m.get("emissif")
        if em and em.get("texture"):
            besoins[em["texture"]] = "couleur"
    for rel, genre in (("textures/T_NM_Blanc.png", "couleur"), ("textures/T_NM_Noir.png", "couleur"),
                       ("textures/T_NM_Normal_Plat.png", "normale"), ("textures/T_NM_ORM_Blanc.png", "lineaire")):
        besoins[rel] = genre

    taches = []
    for rel in besoins:
        nom = os.path.splitext(os.path.basename(rel))[0]
        if EAL.does_asset_exist(DEST_TEX + "/" + nom):
            continue
        t = unreal.AssetImportTask()
        t.set_editor_property("filename", os.path.join(source, rel))
        t.set_editor_property("destination_path", DEST_TEX)
        t.set_editor_property("automated", True)
        t.set_editor_property("replace_existing", True)
        t.set_editor_property("save", False)
        taches.append(t)
    if taches:
        info("Import de %d textures..." % len(taches))
        unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks(taches)

    presents = EAL.list_assets(DEST_TEX, recursive=True, include_folder=False) if EAL.does_directory_exist(DEST_TEX) else []
    res = {}
    for rel, genre in besoins.items():
        nom = os.path.splitext(os.path.basename(rel))[0]
        tex = EAL.load_asset(DEST_TEX + "/" + nom) if EAL.does_asset_exist(DEST_TEX + "/" + nom) else None
        if tex is None:
            for p in presents:
                if p.split("/")[-1].split(".")[0].lower() == nom.lower():
                    tex = EAL.load_asset(p)
                    break
        if tex is None:
            avert("Texture non importée : " + rel)
            continue
        regler_texture(tex, genre)
        res[rel] = tex
    return res


def regler_texture(tex, genre):
    voulu = {
        "normale": (unreal.TextureCompressionSettings.TC_NORMALMAP, False, True),
        "lineaire": (unreal.TextureCompressionSettings.TC_MASKS, False, False),
        "couleur": (unreal.TextureCompressionSettings.TC_DEFAULT, True, False),
    }[genre]
    modif = False
    for prop, val in (("compression_settings", voulu[0]), ("srgb", voulu[1]), ("flip_green_channel", voulu[2])):
        try:
            if tex.get_editor_property(prop) != val:
                tex.set_editor_property(prop, val)
                modif = True
        except Exception as e:
            avert("Texture %s, %s : %s" % (tex.get_name(), prop, e))
    if genre == "normale":
        try:
            tex.set_editor_property("lod_group", unreal.TextureGroup.TEXTUREGROUP_WORLD_NORMAL_MAP)
        except Exception:
            pass
    if modif:
        EAL.save_loaded_asset(tex)


# ------------------------------------------------------------------ matériaux maîtres
def materiau_vide(nom):
    chemin = DEST_MAITRES + "/" + nom
    if EAL.does_asset_exist(chemin):
        mat = EAL.load_asset(chemin)
        MEL.delete_all_material_expressions(mat)
        return mat
    outils = unreal.AssetToolsHelpers.get_asset_tools()
    return outils.create_asset(nom, DEST_MAITRES, unreal.Material, unreal.MaterialFactoryNew())


def noeud(mat, classe, x, y, **props):
    e = MEL.create_material_expression(mat, classe, x, y)
    for k, v in props.items():
        e.set_editor_property(k, v)
    return e


def lier(src, sortie, dst, entree):
    if not MEL.connect_material_expressions(src, sortie, dst, entree):
        avert("Connexion refusée : %s.%s -> %s.%s" % (src.get_name(), sortie, dst.get_name(), entree))


def vers(src, sortie, propriete):
    if not MEL.connect_material_property(src, sortie, propriete):
        avert("Connexion refusée vers %s" % propriete)


def texparam(mat, nom, tex, type_echantillon, x, y):
    return noeud(mat, unreal.MaterialExpressionTextureSampleParameter2D, x, y,
                 parameter_name=nom, texture=tex, sampler_type=type_echantillon)


def creer_maitres(textures):
    blanc = textures.get("textures/T_NM_Blanc.png")
    orm_blanc = textures.get("textures/T_NM_ORM_Blanc.png")
    plat = textures.get("textures/T_NM_Normal_Plat.png")
    if blanc is None or orm_blanc is None or plat is None:
        raise RuntimeError("Textures utilitaires manquantes (T_NM_Blanc, T_NM_ORM_Blanc, T_NM_Normal_Plat).")
    ST = unreal.MaterialSamplerType
    MP = unreal.MaterialProperty

    # --- M_NM_Standard : PBR métal / rugosité ; les instances peuvent passer en « Masked » et en deux faces
    std = materiau_vide("M_NM_Standard")
    std.set_editor_property("blend_mode", unreal.BlendMode.BLEND_OPAQUE)
    std.set_editor_property("shading_model", unreal.MaterialShadingModel.MSM_DEFAULT_LIT)
    std.set_editor_property("opacity_mask_clip_value", 0.5)
    tc = texparam(std, "TexCouleur", blanc, ST.SAMPLERTYPE_COLOR, -900, -400)
    teinte = noeud(std, unreal.MaterialExpressionVectorParameter, -900, -150, parameter_name="Teinte", default_value=unreal.LinearColor(1.0, 1.0, 1.0, 1.0))
    mc = noeud(std, unreal.MaterialExpressionMultiply, -500, -300)
    lier(tc, "RGB", mc, "A")
    lier(teinte, "", mc, "B")
    vers(mc, "", MP.MP_BASE_COLOR)
    vers(tc, "A", MP.MP_OPACITY_MASK)

    torm = texparam(std, "TexORM", orm_blanc, ST.SAMPLERTYPE_MASKS, -900, 100)
    metal = noeud(std, unreal.MaterialExpressionScalarParameter, -900, 350, parameter_name="Metal", default_value=0.0)
    rug = noeud(std, unreal.MaterialExpressionScalarParameter, -900, 450, parameter_name="Rugosite", default_value=1.0)
    occ = noeud(std, unreal.MaterialExpressionScalarParameter, -900, 550, parameter_name="Occlusion", default_value=1.0)
    mm = noeud(std, unreal.MaterialExpressionMultiply, -500, 150)
    lier(torm, "B", mm, "A")
    lier(metal, "", mm, "B")
    vers(mm, "", MP.MP_METALLIC)
    mr = noeud(std, unreal.MaterialExpressionMultiply, -500, 260)
    lier(torm, "G", mr, "A")
    lier(rug, "", mr, "B")
    vers(mr, "", MP.MP_ROUGHNESS)
    lao = noeud(std, unreal.MaterialExpressionLinearInterpolate, -500, 380, const_a=1.0)
    lier(torm, "R", lao, "B")
    lier(occ, "", lao, "Alpha")
    vers(lao, "", MP.MP_AMBIENT_OCCLUSION)

    tn = texparam(std, "TexNormale", plat, ST.SAMPLERTYPE_NORMAL, -900, 700)
    vers(tn, "RGB", MP.MP_NORMAL)

    te = texparam(std, "TexEmissif", blanc, ST.SAMPLERTYPE_COLOR, -900, 950)
    ce = noeud(std, unreal.MaterialExpressionVectorParameter, -900, 1200, parameter_name="CouleurEmissive", default_value=unreal.LinearColor(0.0, 0.0, 0.0, 1.0))
    ie = noeud(std, unreal.MaterialExpressionScalarParameter, -900, 1300, parameter_name="IntensiteEmissive_nits", default_value=0.0)
    me1 = noeud(std, unreal.MaterialExpressionMultiply, -500, 1000)
    lier(te, "RGB", me1, "A")
    lier(ce, "", me1, "B")
    me2 = noeud(std, unreal.MaterialExpressionMultiply, -300, 1050)
    lier(me1, "", me2, "A")
    lier(ie, "", me2, "B")
    vers(me2, "", MP.MP_EMISSIVE_COLOR)
    MEL.layout_material_expressions(std)
    MEL.recompile_material(std)

    # --- M_NM_Verre : translucide éclairé par pixel (reflets spéculaires), opacité plus forte en incidence rasante
    verre = materiau_vide("M_NM_Verre")
    verre.set_editor_property("blend_mode", unreal.BlendMode.BLEND_TRANSLUCENT)
    verre.set_editor_property("shading_model", unreal.MaterialShadingModel.MSM_DEFAULT_LIT)
    verre.set_editor_property("translucency_lighting_mode", unreal.TranslucencyLightingMode.TLM_SURFACE_PER_PIXEL_LIGHTING)
    verre.set_editor_property("two_sided", True)
    vt = noeud(verre, unreal.MaterialExpressionVectorParameter, -700, -200, parameter_name="Teinte", default_value=unreal.LinearColor(0.93, 0.97, 0.95, 1.0))
    vers(vt, "", MP.MP_BASE_COLOR)
    vr = noeud(verre, unreal.MaterialExpressionScalarParameter, -700, 0, parameter_name="Rugosite", default_value=0.04)
    vers(vr, "", MP.MP_ROUGHNESS)
    vo = noeud(verre, unreal.MaterialExpressionScalarParameter, -900, 200, parameter_name="Opacite", default_value=0.14)
    vob = noeud(verre, unreal.MaterialExpressionScalarParameter, -900, 300, parameter_name="OpaciteBord", default_value=0.55)
    fr = noeud(verre, unreal.MaterialExpressionFresnel, -900, 420, exponent=5.0)
    lo = noeud(verre, unreal.MaterialExpressionLinearInterpolate, -500, 250)
    lier(vo, "", lo, "A")
    lier(vob, "", lo, "B")
    lier(fr, "", lo, "Alpha")
    vers(lo, "", MP.MP_OPACITY)
    MEL.layout_material_expressions(verre)
    MEL.recompile_material(verre)

    # --- M_NM_Additif : émission ajoutée à l'image, sans éclairage (flammes, rayon de lumière, poussière)
    add = materiau_vide("M_NM_Additif")
    add.set_editor_property("blend_mode", unreal.BlendMode.BLEND_ADDITIVE)
    add.set_editor_property("shading_model", unreal.MaterialShadingModel.MSM_UNLIT)
    add.set_editor_property("two_sided", True)
    at = texparam(add, "TexEmissif", blanc, ST.SAMPLERTYPE_COLOR, -900, -100)
    ac = noeud(add, unreal.MaterialExpressionVectorParameter, -900, 150, parameter_name="CouleurEmissive", default_value=unreal.LinearColor(1.0, 1.0, 1.0, 1.0))
    ai = noeud(add, unreal.MaterialExpressionScalarParameter, -900, 250, parameter_name="IntensiteEmissive_nits", default_value=1.0)
    am1 = noeud(add, unreal.MaterialExpressionMultiply, -500, 0)
    lier(at, "RGB", am1, "A")
    lier(ac, "", am1, "B")
    am2 = noeud(add, unreal.MaterialExpressionMultiply, -300, 50)
    lier(am1, "", am2, "A")
    lier(ai, "", am2, "B")
    vers(am2, "", MP.MP_EMISSIVE_COLOR)
    MEL.layout_material_expressions(add)
    MEL.recompile_material(add)

    for m in (std, verre, add):
        EAL.save_loaded_asset(m)
    return {"standard": std, "verre": verre, "additif": add}


# ------------------------------------------------------------------ instances de matériaux
def nom_instance(cle):
    return "MI_" + (cle[2:] if cle.startswith("M_") else cle)


def creer_instances(prm, maitres, textures):
    outils = unreal.AssetToolsHelpers.get_asset_tools()
    blanc = textures.get("textures/T_NM_Blanc.png")
    orm_blanc = textures.get("textures/T_NM_ORM_Blanc.png")
    plat = textures.get("textures/T_NM_Normal_Plat.png")
    res = {}
    for cle, d in prm["materiaux"].items():
        nom = nom_instance(cle)
        chemin = DEST_MAT + "/" + nom
        if EAL.does_asset_exist(chemin):
            mi = EAL.load_asset(chemin)
        else:
            mi = outils.create_asset(nom, DEST_MAT, unreal.MaterialInstanceConstant, unreal.MaterialInstanceConstantFactoryNew())
        type_ = d.get("type", "standard")
        parent = maitres["verre"] if type_ == "verre" else (maitres["additif"] if type_ == "additif" else maitres["standard"])
        MEL.set_material_instance_parent(mi, parent)
        em = d.get("emissif") or {}
        tex_em = textures.get(em.get("texture") or "", blanc)
        if type_ == "verre":
            MEL.set_material_instance_vector_parameter_value(mi, "Teinte", lc(d["couleur"][:3]))
            MEL.set_material_instance_scalar_parameter_value(mi, "Opacite", float(d.get("opacite", 0.14)))
            MEL.set_material_instance_scalar_parameter_value(mi, "OpaciteBord", float(d.get("opacite_bord", 0.55)))
            MEL.set_material_instance_scalar_parameter_value(mi, "Rugosite", float(d.get("rugosite", 0.04)))
        elif type_ == "additif":
            MEL.set_material_instance_texture_parameter_value(mi, "TexEmissif", tex_em)
            MEL.set_material_instance_vector_parameter_value(mi, "CouleurEmissive", lc(em.get("couleur", [1, 1, 1])))
            MEL.set_material_instance_scalar_parameter_value(mi, "IntensiteEmissive_nits", float(em.get("intensite_nits", 1.0)))
        else:
            MEL.set_material_instance_texture_parameter_value(mi, "TexCouleur", textures.get(d.get("texture_couleur") or "", blanc))
            MEL.set_material_instance_vector_parameter_value(mi, "Teinte", lc(d.get("couleur", [1, 1, 1, 1])))
            MEL.set_material_instance_texture_parameter_value(mi, "TexORM", textures.get(d.get("texture_orm_unreal") or "", orm_blanc))
            MEL.set_material_instance_scalar_parameter_value(mi, "Metal", float(d.get("metal", 0.0)))
            MEL.set_material_instance_scalar_parameter_value(mi, "Rugosite", float(d.get("rugosite", 0.5)))
            MEL.set_material_instance_scalar_parameter_value(mi, "Occlusion", 1.0 if d.get("occlusion") else 0.0)
            MEL.set_material_instance_texture_parameter_value(mi, "TexNormale", textures.get(d.get("texture_normale") or "", plat))
            MEL.set_material_instance_texture_parameter_value(mi, "TexEmissif", tex_em)
            MEL.set_material_instance_vector_parameter_value(mi, "CouleurEmissive", lc(em.get("couleur", [0, 0, 0])))
            MEL.set_material_instance_scalar_parameter_value(mi, "IntensiteEmissive_nits", float(em.get("intensite_nits", 0.0)))
        # surcharges de l'instance : mode masqué (découpe alpha) et deux faces
        try:
            sur = mi.get_editor_property("base_property_overrides")
            masque = d.get("alpha") == "masque"
            sur.set_editor_property("override_blend_mode", masque)
            if masque:
                sur.set_editor_property("blend_mode", unreal.BlendMode.BLEND_MASKED)
            sur.set_editor_property("override_opacity_mask_clip_value", masque)
            if masque:
                sur.set_editor_property("opacity_mask_clip_value", float(d.get("seuil_alpha", 0.5)))
            deux = bool(d.get("double_face")) and type_ == "standard"
            sur.set_editor_property("override_two_sided", deux)
            if deux:
                sur.set_editor_property("two_sided", True)
            mi.set_editor_property("base_property_overrides", sur)
        except Exception as e:
            avert("Surcharges de %s : %s" % (nom, e))
        MEL.update_material_instance(mi)
        EAL.save_loaded_asset(mi)
        res[cle] = mi
    return res


def assigner_materiaux(prm, instances, composants):
    cles = list(instances.keys())
    poses, oublies = 0, []
    for acteur, comp in composants:
        cles_comp = []
        for i, cands in enumerate(noms_emplacements(comp)):
            k = meilleure_cle(cands, cles)
            if k is None:
                oublies.append("%s[%d]" % (acteur.get_actor_label(), i))
                continue
            comp.set_material(i, instances[k])
            cles_comp.append(k)
            poses += 1
        # un maillage ne projette d'ombre que s'il contient au moins un matériau « opaque » (flammes, verre, rayon : non)
        ombre = any(prm["materiaux"][k].get("ombres", True) for k in cles_comp)
        try:
            comp.set_cast_shadow(ombre)
        except Exception:
            pass
    if oublies:
        avert("Emplacements sans matériau reconnu : " + ", ".join(oublies[:12]))
    return poses


# ------------------------------------------------------------------ lumières
def composants_lumiere():
    res = []
    for a in acteurs():
        if a.get_actor_label().startswith(PREFIXE):
            continue
        try:
            for c in a.get_components_by_class(unreal.LightComponent):
                res.append((a, c))
        except Exception:
            pass
    return res


def identifier_lumieres(prm, lumieres):
    """Associe chaque lumière importée à nos réglages : par le nom si possible, sinon par sa couleur et son intensité."""
    defs = prm["lumieres"]
    res, restants = {}, []
    for a, c in lumieres:
        k = meilleure_cle([a.get_actor_label(), c.get_name()], list(defs.keys()))
        if k and k not in res:
            res[k] = (a, c)
        else:
            restants.append((a, c))
    # repli si les noms n'ont pas survécu à l'import : la directionnelle d'un côté, puis les ponctuelles
    for a, c in restants:
        if isinstance(c, unreal.DirectionalLightComponent):
            for k, v in defs.items():
                if v["type"] == "directional" and k not in res:
                    res[k] = (a, c)
                    break
    points = [(a, c) for a, c in restants if not isinstance(c, unreal.DirectionalLightComponent)]
    bleues = [x for x in points if x[1].get_light_color().b > x[1].get_light_color().r]
    if bleues and "Lueur_Enochienne" in defs and "Lueur_Enochienne" not in res:
        res["Lueur_Enochienne"] = bleues[0]
        points = [x for x in points if x is not bleues[0]]
    # la plus intense importée = la lanterne, les suivantes = les bougies
    libres = sorted([k for k, v in defs.items() if v["type"] != "directional" and k not in res],
                    key=lambda k: -float(defs[k].get("candela", 0.0)))
    points.sort(key=lambda x: -float(x[1].get_editor_property("intensity")))
    for k, x in zip(libres, points):
        res[k] = x
    pris = {id(c) for _, c in res.values()}
    for a, c in lumieres:
        if id(c) not in pris:
            avert("Lumière en trop, non réglée : %s (scène importée deux fois, ou niveau Basic ?). Supprime-la." % a.get_actor_label())
    return res


def regler_lumieres(prm, trouvees):
    if not trouvees:
        avert("Aucune lumière importée : vérifie que le glTF a bien été importé dans le niveau (KHR_lights_punctual).")
        return 0
    for nom, d in prm["lumieres"].items():
        if nom not in trouvees:
            avert("Lumière non retrouvée dans le niveau : " + nom)
            continue
        acteur, c = trouvees[nom]
        try:
            c.set_mobility(unreal.ComponentMobility.MOVABLE)
            c.set_light_color(lc(d["couleur"]), True)   # couleur linéaire, convertie en sRVB par Unreal
            c.set_use_temperature(False)
            if isinstance(c, unreal.DirectionalLightComponent):
                c.set_intensity(float(d["lux"]))
                c.set_light_source_angle(float(d.get("angle_source_deg", 0.5)))
                c.set_atmosphere_sun_light(False)
            else:
                c.set_intensity_units(unreal.LightUnits.CANDELAS)   # d'abord l'unité, ensuite la valeur
                c.set_intensity(float(d["candela"]))
                c.set_attenuation_radius(float(d.get("portee_m", 8.0)) * 100.0)
                c.set_source_radius(float(d.get("rayon_source_m", 0.01)) * 100.0)
                c.set_soft_source_radius(0.0)
                c.set_use_inverse_squared_falloff(True)
            c.set_cast_shadows(bool(d.get("ombres", True)))
            c.set_volumetric_scattering_intensity(float(d.get("volumetrique", 0.0)))
            if isinstance(acteur, unreal.Light):
                acteur.set_actor_label(nom)
        except Exception as e:
            avert("Réglage de la lumière %s : %s" % (nom, e))
    return len(trouvees)


# ------------------------------------------------------------------ caméra
def lire_gltf(source):
    with open(os.path.join(source, "nature_morte.gltf"), encoding="utf-8") as f:
        return json.load(f)


def estimer_repere(source, trouvees):
    """Estime la conversion glTF -> Unreal (permutation signée des axes, x100) à partir des lumières retrouvées."""
    g = lire_gltf(source)
    pos_g = {n.get("name"): n.get("translation") for n in g.get("nodes", []) if n.get("translation")}
    paires = []
    for nom, (acteur, comp) in trouvees.items():
        if nom in pos_g:
            p = comp.get_world_location()
            paires.append((pos_g[nom], (p.x, p.y, p.z)))
    if len(paires) < 3:
        return None
    import itertools
    meilleur, err_min = None, 1e30
    for perm in itertools.permutations(range(3)):
        for signes in itertools.product((1, -1), repeat=3):
            err = 0.0
            for pg, pu in paires:
                for i in range(3):
                    err += (signes[i] * pg[perm[i]] * 100.0 - pu[i]) ** 2
            if err < err_min:
                meilleur, err_min = (perm, signes), err
    if math.sqrt(err_min / len(paires)) > 15.0:
        return None
    return meilleur


def convertir(repere, v):
    perm, signes = repere
    return unreal.Vector(signes[0] * v[perm[0]] * 100.0, signes[1] * v[perm[1]] * 100.0, signes[2] * v[perm[2]] * 100.0)


def direction_gltf(noeud):
    """Axe -Z local d'un nœud glTF : direction d'éclairage d'une lumière, direction de visée d'une caméra."""
    x, y, z, w = noeud.get("rotation", [0.0, 0.0, 0.0, 1.0])
    v = (0.0, 0.0, -1.0)
    t = (2.0 * (y * v[2] - z * v[1]), 2.0 * (z * v[0] - x * v[2]), 2.0 * (x * v[1] - y * v[0]))
    return (v[0] + w * t[0] + (y * t[2] - z * t[1]),
            v[1] + w * t[1] + (z * t[0] - x * t[2]),
            v[2] + w * t[2] + (x * t[1] - y * t[0]))


def verifier_orientations(prm, source, trouvees, camera):
    """L'import doit tourner l'axe -Z des lumières et caméras glTF vers l'axe X d'Unreal. On le vérifie à partir du repère
    estimé sur les positions des lumières, et on corrige au-delà de quelques degrés."""
    repere = estimer_repere(source, trouvees) if trouvees else None
    if repere is None:
        return
    perm, signes = repere
    noeuds = {n.get("name"): n for n in lire_gltf(source).get("nodes", [])}
    for nom, (acteur, comp) in trouvees.items():
        if not isinstance(comp, unreal.DirectionalLightComponent) or nom not in noeuds:
            continue
        dg = direction_gltf(noeuds[nom])
        voulu = unreal.Vector(signes[0] * dg[perm[0]], signes[1] * dg[perm[1]], signes[2] * dg[perm[2]]).normal()
        try:
            if comp.get_forward_vector().dot(voulu) < 0.995:
                comp.set_world_rotation(unreal.MathLibrary.find_look_at_rotation(unreal.Vector(0.0, 0.0, 0.0), voulu), False, False)
                avert("Direction de la lumière %s corrigée d'après le glTF." % nom)
        except Exception as e:
            avert("Vérification de la lumière %s : %s" % (nom, e))
    if camera is None:
        return
    d = prm["camera"]
    try:
        comp = camera.get_cine_camera_component()
        p, c = convertir(repere, d["position"]), convertir(repere, d["cible"])
        if comp.get_forward_vector().dot((c - p).normal()) < 0.999 or (comp.get_world_location() - p).length() > 5.0:
            comp.set_world_location(p, False, False)
            comp.set_world_rotation(unreal.MathLibrary.find_look_at_rotation(p, c), False, False)
            avert("Position ou visée de NM_Camera corrigée d'après le glTF.")
    except Exception as e:
        avert("Vérification de la caméra : %s" % e)


def regler_camera(prm, source, trouvees):
    d = prm["camera"]
    cam = acteur_par_etiquette(PREFIXE + "Camera")
    if cam is None:
        importee = None
        for a in acteurs():
            try:
                comps = a.get_components_by_class(unreal.CameraComponent)
            except Exception:
                comps = []
            if comps:
                importee = (a, comps[0])
                break
        if importee is not None and isinstance(importee[0], unreal.CineCameraActor):
            cam = importee[0]
            cam.set_actor_label(PREFIXE + "Camera")
        else:
            cam = creer_acteur(unreal.CineCameraActor, PREFIXE + "Camera")
            if importee is not None:
                cam.set_actor_location_and_rotation(importee[1].get_world_location(), importee[1].get_world_rotation(), False, False)
            else:
                repere = estimer_repere(source, trouvees)
                if repere is None:
                    avert("Caméra du glTF introuvable : place NM_Camera à la main (voir README, tableau caméra).")
                else:
                    p = convertir(repere, d["position"])
                    c = convertir(repere, d["cible"])
                    rot = unreal.MathLibrary.find_look_at_rotation(p, c)
                    cam.set_actor_location_and_rotation(p, rot, False, False)
    comp = cam.get_cine_camera_component()
    try:
        fb = comp.get_editor_property("filmback")
        fb.set_editor_property("sensor_width", float(d["capteur_mm"][0]))
        fb.set_editor_property("sensor_height", float(d["capteur_mm"][1]))
        comp.set_editor_property("filmback", fb)
        lens = comp.get_editor_property("lens_settings")
        lens.set_editor_property("min_f_stop", 1.2)
        lens.set_editor_property("max_f_stop", 22.0)
        lens.set_editor_property("min_focal_length", 4.0)
        lens.set_editor_property("max_focal_length", 1000.0)
        lens.set_editor_property("diaphragm_blade_count", int(d.get("lames_diaphragme", 7)))
        comp.set_editor_property("lens_settings", lens)
        comp.set_editor_property("current_focal_length", float(d["focale_mm"]))
        comp.set_editor_property("current_aperture", float(d["ouverture_f"]))
        fs = comp.get_editor_property("focus_settings")
        fs.set_editor_property("focus_method", unreal.CameraFocusMethod.MANUAL)
        fs.set_editor_property("manual_focus_distance", float(d["mise_au_point_m"]) * 100.0)
        comp.set_editor_property("focus_settings", fs)
        comp.set_editor_property("constrain_aspect_ratio", True)
    except Exception as e:
        avert("Réglage de la caméra : %s" % e)
    return cam


def regler_mode_de_jeu(camera):
    """En mode Play : aucun personnage (celui du modèle de projet, par exemple First Person) et vue par NM_Camera."""
    try:
        camera.set_editor_property("auto_activate_for_player", unreal.AutoReceiveInput.PLAYER0)
    except Exception as e:
        avert("Activation automatique de NM_Camera en mode Play : %s" % e)
    chemin = DEST + "/BP_NM_GameMode"
    try:
        if not EAL.does_asset_exist(chemin):
            usine = unreal.BlueprintFactory()
            usine.set_editor_property("parent_class", unreal.GameModeBase)
            unreal.AssetToolsHelpers.get_asset_tools().create_asset("BP_NM_GameMode", DEST, unreal.Blueprint, usine)
        classe = EAL.load_blueprint_class(chemin)
        # SpectatorPawn n'a ni maillage ni ombre : rien n'apparaît dans l'image.
        unreal.get_default_object(classe).set_editor_property("default_pawn_class", unreal.SpectatorPawn)
        EAL.save_asset(chemin, only_if_is_dirty=False)
        monde = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
        monde.get_world_settings().set_editor_property("default_game_mode", classe)
    except Exception as e:
        avert("Mode de jeu non réglé (%s) : en mode Play, le personnage du modèle de projet apparaîtra. "
              "Voir LISEZ-MOI, section 4, « Un personnage apparaît en mode Play »." % e)


# ------------------------------------------------------------------ post-process, brouillard, reflets
def creer_postprocess(prm):
    ppv = creer_acteur(unreal.PostProcessVolume, PREFIXE + "PostProcess")
    ppv.set_editor_property("unbound", True)
    ppv.set_editor_property("priority", 10.0)
    ppv.set_editor_property("blend_weight", 1.0)
    s = ppv.get_editor_property("settings")
    post = prm["post"]
    ao = post.get("occlusion_ambiante", {})

    def ov(nom, valeur):
        try:
            s.set_editor_property("override_" + nom, True)
            s.set_editor_property(nom, valeur)
        except Exception as e:
            avert("Post-process %s : %s" % (nom, e))

    ev = float(prm["exposition"]["ev100"])
    ov("auto_exposure_method", unreal.AutoExposureMethod.AEM_MANUAL)
    ov("auto_exposure_apply_physical_camera_exposure", False)   # EV100 de base = 0, réglé par la compensation
    ov("auto_exposure_bias", -ev)                               # -1 = image 2 fois plus sombre = EV100 1
    for nom, val in (("local_exposure_highlight_contrast_scale", 1.0), ("local_exposure_shadow_contrast_scale", 1.0), ("local_exposure_detail_strength", 1.0)):
        ov(nom, val)
    ov("bloom_intensity", float(post["bloom"]["unreal_intensite"]))
    ov("bloom_threshold", float(post["bloom"]["unreal_seuil"]))
    ov("lens_flare_intensity", 0.0)
    ov("vignette_intensity", float(post["vignette"]["unreal_intensite"]))
    ov("film_grain_intensity", float(post["grain"]["unreal_intensite"]))
    ov("scene_fringe_intensity", float(post["aberration_chromatique"]["unreal_intensite"]))
    ov("white_temp", float(post["balance_blancs"]["unreal_temperature_k"]))
    sat = float(post["saturation"]["unreal"])
    con = float(post["contraste"]["unreal"])
    ov("color_saturation", unreal.Vector4(x=sat, y=sat, z=sat, w=1.0))
    ov("color_contrast", unreal.Vector4(x=con, y=con, z=con, w=1.0))
    ov("motion_blur_amount", 0.0)
    ov("ambient_occlusion_intensity", float(ao.get("unreal_intensite", 0.5)))
    ov("ambient_occlusion_radius", float(ao.get("unreal_rayon_cm", 60.0)))
    ov("indirect_lighting_intensity", 1.0)
    ov("dynamic_global_illumination_method", unreal.DynamicGlobalIlluminationMethod.LUMEN)
    ov("reflection_method", unreal.ReflectionMethod.LUMEN)
    ov("lumen_scene_lighting_quality", 1.0)
    ov("lumen_final_gather_quality", 2.0)
    ppv.set_editor_property("settings", s)
    return ppv


def creer_brouillard(prm):
    br = prm["ambiance"]["brouillard"]
    fog = creer_acteur(unreal.ExponentialHeightFog, PREFIXE + "Brouillard")
    c = fog.get_editor_property("component")
    try:
        c.set_fog_density(float(br["unreal_densite"]))
        c.set_fog_height_falloff(float(br["unreal_chute_hauteur"]))
        c.set_start_distance(0.0)
        c.set_fog_max_opacity(1.0)
        c.set_fog_inscattering_color(lc(br["couleur_nits"]))
        c.set_volumetric_fog(False)
    except Exception as e:
        avert("Brouillard : %s" % e)
    for prop in ("directional_inscattering_luminance", "directional_inscattering_color"):
        try:
            c.set_editor_property(prop, unreal.LinearColor(0.0, 0.0, 0.0, 1.0))
            break
        except Exception:
            continue
    return fog


def creer_capture_reflets(composants):
    centre = None
    for a, comp in composants:
        if any("M_Bois_Bureau".lower() in n.lower() for cands in noms_emplacements(comp) for n in cands):
            origine, etendue = a.get_actor_bounds(False)
            centre = unreal.Vector(origine.x, origine.y, origine.z + etendue.z + 30.0)
            break
    cap = creer_acteur(unreal.SphereReflectionCapture, PREFIXE + "Reflets", centre)
    if centre is not None:
        cap.set_actor_location(centre, False, False)
    try:
        cap.get_editor_property("capture_component").set_editor_property("influence_radius", 350.0)
    except Exception as e:
        avert("Capture de reflets : %s" % e)
    return cap


# ------------------------------------------------------------------ capture d'écran
def capturer(camera):
    les = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
    try:
        les.pilot_level_actor(camera)
    except Exception:
        pass
    if not CAPTURE_AUTO:
        return None
    try:
        # La capture haute résolution relance l'accumulation temporelle (Lumen, TSR) : 64 images au lieu de 4 avant la prise.
        monde = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
        unreal.SystemLibrary.execute_console_command(monde, "r.HighResScreenshotDelay 64")
    except Exception as e:
        avert("Délai de capture non réglé (%s) : tape « r.HighResScreenshotDelay 64 » dans la console avant HighResShot." % e)
    try:
        unreal.AutomationLibrary.take_high_res_screenshot(RESOLUTION_CAPTURE[0], RESOLUTION_CAPTURE[1], "nature_morte_unreal.png",
                                                           camera=camera, delay=3.0)
        return "Saved/Screenshots (dossier de la plateforme), fichier nature_morte_unreal.png"
    except Exception as e:
        avert("Capture automatique impossible (%s) : pilote NM_Camera, touche G, puis tape « r.HighResScreenshotDelay 64 » et "
              "« HighResShot 1920x1080 » dans la console." % e)
        return None


# ------------------------------------------------------------------ programme principal
def main():
    del AVERTISSEMENTS[:]
    source = trouver_source()
    with open(os.path.join(source, "parametres_rendu.json"), encoding="utf-8") as f:
        prm = json.load(f)
    info("Source : " + source)

    composants = composants_scene(prm)
    lance = None
    if not composants:
        info("Scène non trouvée dans le niveau : import du glTF...")
        lance = importer_scene(source)
        composants = composants_scene(prm)
    if not composants:
        if lance == "deja":
            msg = ("Les maillages de la scène existent déjà dans " + DEST_IMPORT + ", mais ils ne sont pas dans ce niveau.\n\n"
                   "Ouvre le niveau où tu as importé la scène (Content/NatureMorte/Maps/NatureMorte) et relance le script. "
                   "Pour repartir de zéro : supprime le dossier " + DEST_IMPORT + ", fais File > Import Into Level... dans un niveau vide, "
                   "puis relance le script.")
        elif lance:
            msg = ("Import lancé : il se termine en arrière-plan (barre de progression en bas à droite de l'éditeur).\n\n"
                   "Attends la fin, NE refais PAS File > Import Into Level (la scène serait en double), puis relance le script.")
        else:
            msg = ("La scène n'est pas encore dans le niveau.\n\nFais File > Import Into Level..., choisis "
                   + os.path.join(source, "nature_morte.gltf") + ", attends la fin de l'import puis relance le script.")
        unreal.EditorDialog.show_message("Nature morte", msg, unreal.AppMsgType.OK)
        return
    verifier_niveau(composants)

    with unreal.ScopedSlowTask(8, "Nature morte") as tache:
        tache.make_dialog(True)
        tache.enter_progress_frame(1, "Textures")
        textures = importer_textures(source, prm)
        tache.enter_progress_frame(1, "Matériaux maîtres")
        maitres = creer_maitres(textures)
        tache.enter_progress_frame(1, "Instances de matériaux")
        instances = creer_instances(prm, maitres, textures)
        tache.enter_progress_frame(1, "Affectation des matériaux")
        poses = assigner_materiaux(prm, instances, composants)
        tache.enter_progress_frame(1, "Lumières")
        lumieres = composants_lumiere()
        trouvees = identifier_lumieres(prm, lumieres) if lumieres else {}
        nb_lum = regler_lumieres(prm, trouvees)
        tache.enter_progress_frame(1, "Caméra")
        camera = regler_camera(prm, source, trouvees)
        verifier_orientations(prm, source, trouvees, camera)
        regler_mode_de_jeu(camera)
        tache.enter_progress_frame(1, "Post-process et atmosphère")
        creer_postprocess(prm)
        creer_brouillard(prm)
        creer_capture_reflets(composants)
        tache.enter_progress_frame(1, "Enregistrement")
        EAL.save_directory(DEST, only_if_is_dirty=True, recursive=True)
        try:
            enregistre = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).save_current_level()
        except Exception:
            enregistre = False
        if not enregistre:
            avert("Niveau non enregistré automatiquement : fais File > Save Current Level As... dans /Game/NatureMorte/Maps.")

    ou = capturer(camera)
    resume = ["Scène réglée : %d matériaux posés sur %d maillages, %d lumières, exposition EV100 %.2f (Exposure Compensation %.2f)."
              % (poses, len(composants), nb_lum, float(prm["exposition"]["ev100"]), -float(prm["exposition"]["ev100"]))]
    if ou:
        resume.append("La capture sera prise quelques secondes après la fermeture de cette fenêtre : " + ou)
    if AVERTISSEMENTS:
        resume.append("%d remarque(s), voir l'Output Log." % len(AVERTISSEMENTS))
    info(" ".join(resume))
    unreal.EditorDialog.show_message("Nature morte", "\n\n".join(resume), unreal.AppMsgType.OK)


main()
