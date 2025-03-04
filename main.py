import json
import os
import logging
import random
from typing import List, Dict, Any, Union

import streamlit as st

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")


def load_categories(folder_path: str = "qcm") -> Dict[str, Dict[str, str]]:
    """
    Charge les catégories disponibles à partir du dossier QCM.
    Chaque catégorie est un sous-dossier contenant un ou plusieurs fichiers JSON de QCM.
    
    Retourne:
        Un dictionnaire associant le nom de la catégorie à un dictionnaire qui associe le titre du QCM au chemin du fichier.
    """
    categories = {}
    if not os.path.exists(folder_path):
        os.makedirs(folder_path)
        st.warning(f"Dossier '{folder_path}' créé. Veuillez ajouter des sous-dossiers de catégories contenant des fichiers QCM JSON.")
        logging.info("Created missing folder '%s'.", folder_path)
        return categories

    for category in os.listdir(folder_path):
        category_path = os.path.join(folder_path, category)
        if os.path.isdir(category_path):
            qcms = {}
            for filename in os.listdir(category_path):
                if filename.endswith('.json'):
                    file_path = os.path.join(category_path, filename)
                    try:
                        with open(file_path, "r", encoding="utf-8") as f:
                            data = json.load(f)
                        qcm_title = get_qcm_title(data) or filename.replace('.json', '')
                        qcms[qcm_title] = file_path
                    except Exception as e:
                        st.warning(f"Fichier '{filename}' dans '{category}' ignoré : {str(e)}")
                        logging.error("Error loading file %s in category %s: %s", filename, category, str(e))
            if qcms:
                categories[category] = qcms
    return categories


def get_qcm_title(data: Any) -> str:
    """
    Extrait le titre du QCM à partir des données JSON.
    """
    if isinstance(data, list) and data:
        if isinstance(data[0], dict) and "titre_qcm" in data[0]:
            return data[0]["titre_qcm"]
    if isinstance(data, dict) and "metadata" in data and "titre" in data["metadata"]:
        return data["metadata"]["titre"]
    return ""


def load_qcm_data(file_path: str) -> Dict[str, Any]:
    """
    Charge les données du QCM à partir d'un fichier JSON et valide leur structure.
    
    Retourne:
        Un dictionnaire contenant 'metadata' et 'questions'.
    """
    try:
        if not os.path.exists(file_path):
            st.error(f"Fichier {file_path} introuvable.")
            logging.error("File not found: %s", file_path)
            return {"metadata": {}, "questions": []}
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        metadata = {}
        questions = []
        
        if isinstance(data, dict):
            # Nouveau format avec metadata et questions
            metadata = data.get("metadata", {})
            questions = data.get("questions", [])
        elif isinstance(data, list):
            # Format ancien : liste de questions, vérifier le titre dans la première question
            questions = data
            if questions and isinstance(questions[0], dict) and "titre_qcm" in questions[0]:
                metadata["titre"] = questions[0].get("titre_qcm", "")
        else:
            raise ValueError("Structure du QCM invalide ; une liste ou un dictionnaire avec 'questions' était attendu.")
        
        validate_qcm_data(questions)
        return {"metadata": metadata, "questions": questions}
    except json.JSONDecodeError:
        st.error(f"Le fichier {file_path} n'est pas un JSON valide.")
        logging.exception("JSON decode error in file: %s", file_path)
        return {"metadata": {}, "questions": []}
    except Exception as e:
        st.error(f"Erreur lors du chargement du QCM : {str(e)}")
        logging.exception("Error loading QCM from %s", file_path)
        return {"metadata": {}, "questions": []}


def validate_qcm_data(data: Any) -> None:
    """
    Valide la structure des données du QCM.
    
    Lève:
        ValueError si le format des données est invalide.
    """
    if not isinstance(data, list):
        raise ValueError("Les données du QCM doivent être une liste de questions.")
        
    required_keys = ["enonce", "possibilites", "bonne_reponse"]
    for i, question in enumerate(data):
        if not isinstance(question, dict):
            raise ValueError(f"La question {i+1} n'est pas un dictionnaire valide.")
        for key in required_keys:
            if key not in question:
                raise ValueError(f"La question {i+1} est dépourvue de la clé requise '{key}'.")
        
        correct = question["bonne_reponse"]
        if isinstance(correct, int):
            if correct < 0 or correct >= len(question["possibilites"]):
                raise ValueError(f"La question {i+1} a un index de bonne réponse hors limites.")
        elif isinstance(correct, str):
            if correct not in question["possibilites"]:
                raise ValueError(f"La question {i+1} a une bonne réponse qui ne figure pas parmi les possibilités.")
        else:
            raise ValueError(f"La 'bonne_reponse' de la question {i+1} doit être un entier ou une chaîne de caractères.")


def initialize_session_state() -> None:
    """Initialise les variables d'état de session de Streamlit."""
    defaults = {
        "question_index": 0,
        "score": 0,
        "answered_questions": set(),
        "selected_category": None,
        "current_qcm": None,
        "aggregated_qcms": None,
        "qcm_selected": False,
        "error_occurred": False,
        "error_message": "",
        "qcm_data": None
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def reset_qcm_state() -> None:
    """Réinitialise l'état du quiz pour démarrer un nouveau QCM."""
    st.session_state["question_index"] = 0
    st.session_state["score"] = 0
    st.session_state["answered_questions"] = set()
    st.session_state["qcm_selected"] = True
    st.session_state["error_occurred"] = False
    st.session_state["error_message"] = ""
    st.session_state["qcm_data"] = None 


def display_question(question: Dict[str, Any]) -> Union[str, None]:
    """
    Affiche la question en cours et retourne la sélection de l'utilisateur.
    """
    current_index = st.session_state["question_index"]
    radio_key = f"radio_{current_index}"
    
    if radio_key not in st.session_state:
        st.session_state[radio_key] = question["possibilites"][0]

    st.markdown(f"### Question {current_index + 1}")
    st.write(question["enonce"])
    
    user_choice = st.radio(
        "Sélectionnez votre réponse :",
        question["possibilites"],
        index=0,
        key=radio_key
    )
    
    return user_choice


def check_answer(question: Dict[str, Any], user_choice: str) -> bool:
    """
    Vérifie si la réponse sélectionnée est correcte.
    
    Si 'bonne_reponse' est un entier, il est traité comme un index ;
    s'il s'agit d'une chaîne, une comparaison directe est effectuée.
    """
    try:
        correct = question["bonne_reponse"]
        if isinstance(correct, int):
            choice_index = question["possibilites"].index(user_choice)
            return choice_index == correct
        elif isinstance(correct, str):
            return user_choice.strip() == correct.strip()
        else:
            st.error("Type invalide pour 'bonne_reponse'.")
            return False
    except ValueError:
        st.error("Sélection de réponse invalide.")
        logging.error("Invalid answer selected: %s", user_choice)
        return False


def display_score(total_questions: int) -> None:
    """
    Affiche le score actuel et la progression.
    """
    st.sidebar.markdown("## Progression")
    progress = st.session_state["question_index"] / total_questions if total_questions else 0
    st.sidebar.progress(progress)
    denominator = max(1, st.session_state["question_index"])
    st.sidebar.markdown(f"**Score actuel** : {st.session_state['score']}/{denominator}")


def display_final_score(total_questions: int, qcm_title: str) -> None:
    """
    Affiche le score final et offre des options pour redémarrer ou choisir un autre quiz.
    """
    st.markdown(f"## 🎉 Fin du QCM : {qcm_title}")
    st.markdown(f"**Score final** : {st.session_state['score']}/{total_questions}")
    if total_questions > 0:
        percentage = (st.session_state['score'] / total_questions) * 100
        if percentage >= 80:
            st.success(f"Excellent ! Vous avez obtenu {percentage:.1f}%.")
        elif percentage >= 60:
            st.info(f"Bien joué ! Vous avez obtenu {percentage:.1f}%.")
        else:
            st.warning(f"Vous avez obtenu {percentage:.1f}%. Continuez à vous entraîner !")
    col1, col2 = st.columns(2)
    with col1:
        if st.button("Recommencer ce QCM", key="restart_qcm"):
            reset_qcm_state()
            st.rerun()
    with col2:
        if st.button("Choisir un autre QCM", key="choose_another_qcm"):
            st.session_state["current_qcm"] = None
            st.session_state["aggregated_qcms"] = None
            st.rerun()


def category_selector() -> None:
    """
    Affiche les catégories disponibles pour sélection.
    """
    st.title("Catégories de QCM")
    categories = load_categories("qcm")
    if not categories:
        st.warning("Aucune catégorie trouvée dans le dossier 'qcm'. Veuillez ajouter des dossiers de catégories contenant des fichiers QCM.")
        return
    for category in categories.keys():
        if st.button(f"Sélectionner la catégorie : {category}", key=f"select_category_{category}"):
            st.session_state["selected_category"] = category
            st.rerun()


def qcm_selector() -> None:
    """
    Affiche les QCM disponibles dans la catégorie choisie.
    Offre une option pour un quiz agrégé si plusieurs QCM existent.
    """
    st.title(f"Catégorie : {st.session_state['selected_category']}")
    st.markdown("### Choisissez un QCM ou lancez un quiz agrégé :")
    categories = load_categories("qcm")
    current_category = st.session_state["selected_category"]
    if current_category not in categories:
        st.error("Catégorie sélectionnée introuvable.")
        return
    qcms = categories[current_category]
    if len(qcms) > 1:
        if st.button("Lancer un QCM agrégé (tous les quiz)", key="aggregated_qcm"):
            st.session_state["aggregated_qcms"] = list(qcms.values())
            reset_qcm_state()
            st.rerun()
    for qcm_title, file_path in qcms.items():
        if st.button(f"Démarrer : {qcm_title}", key=f"start_qcm_{qcm_title}"):
            st.session_state["current_qcm"] = file_path
            st.session_state["aggregated_qcms"] = None
            reset_qcm_state()
            st.rerun()
    if st.button("⬅️ Retour aux catégories", key="back_to_categories"):
        st.session_state["selected_category"] = None
        st.rerun()


def run_qcm() -> None:
    if st.session_state["qcm_data"] is None:
        qcm_data = []
        metadata = {}
        qcm_title = "QCM sans titre"
        if st.session_state["aggregated_qcms"]:
            aggregated_titles = []
            for file_path in st.session_state["aggregated_qcms"]:
                data = load_qcm_data(file_path)
                if data["questions"]:
                    qcm_data.extend(data["questions"])
                    title = data["metadata"].get("titre", os.path.basename(file_path).replace('.json', ''))
                    aggregated_titles.append(title)
            qcm_title = f"QCM agrégé ({', '.join(aggregated_titles)})"
        else:
            data = load_qcm_data(st.session_state["current_qcm"])
            qcm_data = data["questions"]
            metadata = data["metadata"]
            qcm_title = metadata.get("titre", os.path.basename(st.session_state["current_qcm"]).replace('.json', ''))
        
        if not qcm_data:
            st.error("Aucune donnée QCM valide disponible.")
            if st.button("Retour à la sélection de QCM"):
                st.session_state["current_qcm"] = None
                st.session_state["aggregated_qcms"] = None
                st.rerun()
            return
        
        random.shuffle(qcm_data)
        st.session_state["qcm_data"] = qcm_data
        st.session_state["qcm_title"] = qcm_title
    else:
        qcm_data = st.session_state["qcm_data"]
        qcm_title = st.session_state["qcm_title"]

    st.title(f"QCM : {qcm_title}")
    display_score(len(qcm_data))
    
    if st.session_state["question_index"] >= len(qcm_data):
        display_final_score(len(qcm_data), qcm_title)
        return

    if st.session_state.get("error_occurred", False):
        st.error(st.session_state["error_message"])
        if st.button("Question suivante", key="next_question"):
            st.session_state["question_index"] += 1
            st.session_state["error_occurred"] = False
            st.session_state["error_message"] = ""
            st.rerun()
        return

    current_question = qcm_data[st.session_state["question_index"]]
    user_choice = display_question(current_question)
    
    col1, col2 = st.columns([1, 3])
    with col1:
        if st.button("Valider", key=f"submit_{st.session_state['question_index']}"):
            if check_answer(current_question, user_choice):
                st.success("✅ Bonne réponse !")
                st.session_state["score"] += 1
                st.session_state["answered_questions"].add(st.session_state["question_index"])
                st.session_state["question_index"] += 1
                st.rerun()
            else:
                correct = current_question["bonne_reponse"]
                if isinstance(correct, int):
                    correct_answer = current_question["possibilites"][correct]
                elif isinstance(correct, str):
                    correct_answer = correct
                else:
                    correct_answer = "Inconnue"
                st.session_state["error_occurred"] = True
                st.session_state["error_message"] = f"❌ Incorrect. La bonne réponse était : {correct_answer}"
                st.rerun()
    with col2:
        if st.button("Passer cette question", key=f"skip_{st.session_state['question_index']}"):
            st.session_state["question_index"] += 1
            st.rerun()


def main():
    """
    Fonction principale pour contrôler la navigation :
      - Sélection de la catégorie (si non choisie)
      - Sélection du QCM au sein d'une catégorie
      - Exécution du QCM sélectionné ou agrégé.
    """
    st.set_page_config(page_title="Application QCM", page_icon="📝", layout="centered")
    initialize_session_state()
    
    if st.session_state.get("selected_category"):
        st.sidebar.markdown(f"**Catégorie :** {st.session_state['selected_category']}")
        if st.sidebar.button("⬅️ Retour aux catégories", key="sidebar_back_to_categories"):
            st.session_state["selected_category"] = None
            st.session_state["current_qcm"] = None
            st.session_state["aggregated_qcms"] = None
            st.rerun()
    if st.session_state.get("qcm_selected"):
        if st.sidebar.button("⬅️ Retour à la sélection de QCM", key="sidebar_back_to_qcm_selection"):
            st.session_state["current_qcm"] = None
            st.session_state["aggregated_qcms"] = None
            st.rerun()
    
    if not st.session_state.get("selected_category"):
        category_selector()
    elif not st.session_state.get("current_qcm") and not st.session_state.get("aggregated_qcms"):
        qcm_selector()
    else:
        run_qcm()


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        logging.exception("Unexpected error: %s", str(e))
        st.error("Une erreur inattendue est survenue. Consultez les logs pour plus de détails.")
