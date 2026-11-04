"""Render the French assignment report from reproducible local evidence."""

import argparse
import json
from pathlib import Path
from textwrap import fill

import matplotlib
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
from matplotlib.image import imread
from matplotlib.patches import FancyBboxPatch

matplotlib.use("Agg")

REPORTS = Path("reports")
FIGURES = REPORTS / "figures"
INK = "#202b3a"
ACCENT = "#1c6357"


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def page(pdf, number, title, sections, figure=None):
    fig = plt.figure(figsize=(8.27, 11.69), facecolor="white")
    fig.text(0.09, 0.947, "MLOPS   /   ANALYSE DE SENTIMENT YOUTUBE", color=ACCENT,
             fontsize=9, weight="bold")
    fig.text(0.09, 0.898, title, color=INK, fontsize=25, weight="bold")
    cursor = 0.825
    for heading, content in sections:
        fig.text(0.09, cursor, heading, color=ACCENT, fontsize=12, weight="bold", va="top")
        body = fill(content, width=84)
        fig.text(0.09, cursor - 0.027, body, color=INK, fontsize=10, va="top", linespacing=1.45)
        cursor -= 0.062 + 0.017 * len(body.splitlines())
    if figure and figure.is_file():
        image = imread(figure)
        bottom = 0.115
        height = min(0.35, cursor - bottom)
        if height > 0.09:
            ax = fig.add_axes([0.09, bottom, 0.82, height])
            ax.imshow(image)
            ax.axis("off")
    fig.text(0.09, 0.05, "TP Cloud Computing   /   INDIA S5", color=ACCENT, fontsize=8)
    fig.text(0.91, 0.05, f"{number:02d} / 08", ha="right", color=ACCENT, fontsize=8)
    pdf.savefig(fig)
    plt.close(fig)


def confusion_image(metrics):
    fig, ax = plt.subplots(figsize=(6.1, 4.1), layout="constrained")
    matrix = metrics["confusion_matrix"]
    ax.imshow(matrix, cmap="Blues")
    names = ["Négatif", "Neutre", "Positif"]
    ax.set(xticks=range(3), yticks=range(3), xticklabels=names, yticklabels=names,
           xlabel="Prédiction", ylabel="Annotation", title="Matrice de confusion sur le test Reddit")
    cutoff = max(map(max, matrix)) / 2
    for row in range(3):
        for col in range(3):
            val = matrix[row][col]
            ax.text(col, row, str(val), ha="center", va="center", color="white" if val > cutoff else INK)
    output = FIGURES / "confusion.png"
    fig.savefig(output, dpi=160)
    plt.close(fig)
    return output


def architecture_image():
    fig, ax = plt.subplots(figsize=(9.5, 3.5), layout="constrained")
    ax.set(xlim=(0, 1), ylim=(0, 1))
    ax.axis("off")
    positions = [0.13, 0.37, 0.61, 0.85]
    serving_y, training_y = 0.69, 0.21
    width, height = 0.178, 0.215
    rows = [
        (serving_y, ["YouTube", "Extension\nChrome", "API\nFastAPI", "Pipeline\nTF-IDF + RL"]),
        (training_y, ["CSV\nReddit", "Nettoyage\net split", "Validation\ncroisée", "Artefact\nJoblib"]),
    ]
    ax.text(0.04, 0.92, "PRÉDICTION", color=ACCENT, fontsize=10, weight="bold")
    ax.text(0.04, 0.44, "ENTRAÎNEMENT", color=ACCENT, fontsize=10, weight="bold")
    for y, labels in rows:
        for i, (x, label) in enumerate(zip(positions, labels, strict=True)):
            ax.add_patch(FancyBboxPatch(
                (x - width / 2, y - height / 2), width, height,
                boxstyle="round,pad=0.009", fc="#edf6f4", ec="#84aea6", lw=1.1,
            ))
            ax.text(x, y, label, color=INK, ha="center", va="center", fontsize=11)
            if i < len(labels) - 1:
                ax.annotate("", (positions[i + 1] - 0.093, y), (x + 0.093, y),
                            arrowprops={"arrowstyle": "->", "color": ACCENT, "lw": 1.2})
    ax.annotate("", (positions[-1], serving_y - 0.12), (positions[-1], training_y + 0.12),
                arrowprops={"arrowstyle": "->", "color": ACCENT, "lw": 1.2})
    output = FIGURES / "architecture.png"
    fig.savefig(output, dpi=180)
    plt.close(fig)
    return output


def build(output: Path):
    metrics = read_json(REPORTS / "metrics.json")
    model = read_json(Path("models/metadata.json"))
    data = model["data"]
    cv = metrics["cv_macro_f1"]
    classes = metrics["classification_report"]
    speed = metrics["benchmark"]
    limits = [
        (metrics["accuracy"] >= 0.80, "exactitude"),
        (all(classes[key]["f1-score"] > 0.75 for key in ("negative", "neutral", "positive")), "F1 par classe"),
        (speed["p95_ms"] < 100, "latence p95"),
    ]
    failed = [label for passed, label in limits if not passed]
    verdict = "Objectifs mesurés atteints." if not failed else "Objectifs à améliorer : " + ", ".join(failed) + "."
    FIGURES.mkdir(parents=True, exist_ok=True)
    chart = confusion_image(metrics)
    architecture = architecture_image()
    output.parent.mkdir(parents=True, exist_ok=True)
    with PdfPages(output, metadata={"Title": "Analyse de sentiment YouTube", "Subject": "TP Cloud Computing"}) as pdf:
        page(pdf, 1, "Analyse de sentiment YouTube", [
            ("Contexte", "Une vidéo peut recevoir des centaines de commentaires. Le projet regroupe les "
             "prédictions négatives, neutres et positives pour aider à parcourir les réactions."),
            ("Architecture", "L’extension Chrome extrait les commentaires déjà affichés. Son service worker "
             "les transmet par lots à FastAPI. Le modèle scikit-learn renvoie un sentiment et une probabilité "
             "par commentaire. Le popup présente la répartition et permet de filtrer et d’exporter les résultats."),
            ("Résumé expérimental", f"Le modèle {model['model_version']} atteint {metrics['accuracy']:.2%} "
             f"d’exactitude sur {data['test_rows']:,} commentaires Reddit de test. L’inférence d’un lot de 50 "
             f"commentaires a un p95 de {speed['p95_ms']:.2f} ms. {verdict}"),
        ], architecture)
        page(pdf, 2, "Données et préparation", [
            ("Acquisition", "La source de référence est le fichier reddit.csv du dépôt "
             "Himanshu-1703/reddit-sentiment-analysis. Le téléchargement conserve le CSV brut et enregistre "
             "son empreinte SHA-256. La copie locale utilisée et le CSV en ligne ont été comparés : les textes normalisés et les labels sont identiques. Les colonnes clean_comment et category deviennent text et label."),
            ("Nettoyage", "Normalisation Unicode, suppression des URL et mentions, conversion des emojis "
             "pris en charge en tokens et conservation des mots de négation. Les textes vides et les "
             "doublons normalisés sont supprimés avant la séparation. Les conflits de labels sont écartés."),
            ("Séparation", f"{data['usable_rows']:,} commentaires utilisables après préparation. La séparation "
             f"stratifiée 80/20 produit {data['train_rows']:,} exemples d’apprentissage et "
             f"{data['test_rows']:,} de test, avec la graine {data['seed']}. Les textes identiques après "
             "normalisation ne peuvent pas se retrouver des deux côtés."),
        ], FIGURES / "dataset.png")
        page(pdf, 3, "Entraînement et sélection", [
            ("TF-IDF", "La fréquence locale est pondérée par la rareté du terme dans les documents "
             "d’apprentissage. La recherche compare des n-grammes de mots seuls et une combinaison avec "
             "des n-grammes de caractères, utiles pour certaines variantes orthographiques."),
            ("Comparaison", f"Validation croisée stratifiée à trois plis. F1 macro de la référence "
             f"majoritaire : {cv['majority']:.3f}. SVM linéaire : {cv['linear_svm']:.3f}. "
             f"Meilleure régression logistique : {cv['best_logistic_regression']:.3f}."),
            ("Optimisation", f"Recherche de {len(metrics['trials'])} configurations par grille, notamment "
             "la régularisation C, la pondération des classes et les caractéristiques TF-IDF. La "
             "vectorisation est apprise dans chaque pli. Le choix final s’appuie sur le F1 macro "
             "de validation, puis la configuration choisie est réentraînée sur la partition d’apprentissage."),
            ("Artefacts", "Le pipeline complet est utilisé par l’API. Le classificateur et le vectoriseur "
             "sont également exportés séparément. Les versions de dépendances, les paramètres et le hash "
             "du pipeline figurent dans models/metadata.json."),
        ])
        page(pdf, 4, "Résultats sur le test", [
            ("Qualité", f"Exactitude {metrics['accuracy']:.2%}. F1 négatif {classes['negative']['f1-score']:.3f}, "
             f"neutre {classes['neutral']['f1-score']:.3f}, positif {classes['positive']['f1-score']:.3f}. "
             f"F1 macro {classes['macro avg']['f1-score']:.3f}. {verdict}"),
            ("Vitesse", f"Lots de {speed['batch_size']} commentaires, {speed['repetitions']} essais à chaud. "
             f"Moyenne {speed['mean_ms']:.2f} ms et p95 {speed['p95_ms']:.2f} ms. Cette mesure couvre le "
             "nettoyage, la vectorisation et le calcul des probabilités. Le délai HTTP est mesuré séparément."),
        ], chart)
        page(pdf, 5, "API de prédiction", [
            ("Contrat", "GET /health indique si le modèle est prêt et renvoie sa version. POST /predict_batch "
             "accepte de 1 à 50 éléments id/text. Les identifiants sont uniques dans le lot et les textes "
             "sont limités à 5 000 caractères."),
            ("Prédictions", "L’ordre des commentaires est conservé. Chaque prédiction contient le label, "
             "son nom et la probabilité de la classe sélectionnée. Un texte devenu vide est signalé "
             "comme ignoré et exclu du calcul des pourcentages."),
            ("Disponibilité", "Le modèle est chargé une fois au démarrage et son empreinte est vérifiée. "
             "Une requête invalide renvoie 422. Un modèle indisponible donne 503. La durée et la taille "
             "du lot sont journalisées sans les textes des utilisateurs."),
            ("Configuration", "Le middleware CORS peut autoriser les origines d’extension explicites. "
             "La documentation interactive générée par FastAPI est accessible sous /docs."),
        ])
        page(pdf, 6, "Extension Chrome", [
            ("Collecte", "Un script de contenu lit les commentaires chargés dans la page de lecture, y "
             "compris les réponses dépliées. L’utilisateur défile pour charger davantage de commentaires "
             "avant une nouvelle analyse. Le plafond est de 250 commentaires par analyse."),
            ("Traitement", "Le service worker envoie des lots de 50 et stocke leur progression par onglet "
             "et vidéo. Les erreurs réseau et les résultats partiels sont visibles après réouverture du popup."),
            ("Interface", "Le popup présente une barre de répartition, des filtres, les probabilités, "
             "un thème clair/sombre, la copie et l’export JSON. Les commentaires sont insérés comme texte."),
        ], Path("docs/screenshots/popup-light.png"))
        page(pdf, 7, "Déploiement et validation", [
            ("Conteneur", "Docker utilise Python 3.13, les dépendances verrouillées et un utilisateur "
             "sans privilèges. Uvicorn écoute sur le port 7860. L’image embarque le pipeline de service "
             "et ne requiert aucun téléchargement de données à l’exécution."),
            ("Mise en ligne", "Le dépôt contient la configuration Hugging Face Docker Spaces et le script "
             "de publication. Le lancement de l’instance hébergée requiert un compte autorisé. Après publication, "
             "vérifier /health, un lot de prédictions et l’extension configurée avec l’origine HTTPS du Space."),
            ("Contrôles", "Les tests valident les entrées API, les classes et probabilités, les textes ignorés, "
             "les erreurs, la taille maximale de lot, le regroupement des résultats et le changement de vidéo. "
             "Le test navigateur Playwright utilise une page de commentaires contrôlée et l’API locale."),
            ("Reproductibilité", "Les commandes dans le README recréent les splits, le modèle, les figures et "
             "le paquet d’extension. Le workflow CI prévoit également le démarrage du conteneur et son test de santé."),
        ])
        page(pdf, 8, "Limites et pistes de travail", [
            ("Transfert Reddit vers YouTube", "Les scores du test Reddit quantifient la performance sur la "
             "distribution annotée de référence. Les usages, la langue et les formulations sur YouTube "
             "peuvent différer. Annoter un échantillon YouTube indépendant pour mesurer ce transfert."),
            ("Interprétation", "La probabilité d’une classe est une sortie du modèle. L’ironie, les textes "
             "très courts et la langue mélangée restent difficiles. Une étude de calibration et de couverture "
             "linguistique aiderait à interpréter les scores."),
            ("Robustesse", "YouTube peut modifier ses composants. L’extraction repose sur des sélecteurs "
             "explicites à vérifier sur plusieurs vidéos. La taille des lots et les limites de collecte "
             "réduisent le coût des requêtes et du rendu."),
            ("Sources et livrables", "Consigne TP Cloud Computing INDIA S5, jeu Reddit indiqué dans le sujet, "
             "documentation officielle scikit-learn, FastAPI, Chrome Extensions et Hugging Face Docker Spaces. "
             "Les fichiers metrics.json et metadata.json contiennent les résultats et la provenance détaillée."),
        ])


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Build the technical report PDF")
    parser.add_argument("--output", type=Path, default=REPORTS / "rapport-technique.pdf")
    args = parser.parse_args()
    build(args.output)
