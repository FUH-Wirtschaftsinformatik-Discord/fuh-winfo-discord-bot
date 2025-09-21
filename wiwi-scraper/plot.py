import matplotlib.pyplot as plt
import pandas as pd
from peewee import Case

from wiwi_models import StudyModuleModel

module_number="31831"
# module_number="31831"

# Load all StudyModuleModel objects into memory (example for module_number == "31831")
# Order by year, then is_summer_semester (1 first), then examination_period with P2 last using peewee.Case
all_study_modules = list(
    StudyModuleModel.select()
    .where(StudyModuleModel.module_number == module_number)
    .order_by(
        StudyModuleModel.year,
        StudyModuleModel.is_summer_semester.asc(),
        Case(None, ((StudyModuleModel.examination_period == "P2", 1),), 0)
    )
)

if len(all_study_modules) == 0:
    print(f"No data found for module_number={module_number}")
    exit(1)

module_name=all_study_modules[0].module_name

semester_labels: list[str] = []
participant_labels: list[int] = []
very_good_labels: list[int] = []
good_labels: list[int] = []
satisfactory_labels: list[int] = []
sufficient_labels: list[int] = []
insufficient_labels: list[int] = []

for module in all_study_modules:
   
    fmodule_name=""

    if module.is_summer_semester:
        fmodule_name = f"SS{module.year}"
    else:
        fmodule_name = f"WS{module.year-1}/{module.year}"

    print(f"{fmodule_name} {module.examination_period}: Teilnehmer={module.very_good + module.good + module.satisfactory + module.sufficient + module.insufficient}")

    semester_labels.append(f"{fmodule_name} {module.examination_period}")
    participants = module.very_good + module.good + module.satisfactory + module.sufficient + module.insufficient
    participant_labels.append(participants)
    very_good_labels.append(module.very_good)   
    good_labels.append(module.good)
    satisfactory_labels.append(module.satisfactory)
    sufficient_labels.append(module.sufficient)
    insufficient_labels.append(module.insufficient)

data = {
    "Name": module_name,
    "Modulnummer": module_number,
    "Semester": semester_labels,
    "Teilnehmer": participant_labels,
    "sehr gut": very_good_labels,
    "gut": good_labels,
    "befriedigend": satisfactory_labels,
    "ausreichend": sufficient_labels,
    "nicht ausreichend": insufficient_labels
}

def create_combined_diagram(data):
    df = pd.DataFrame(data)
    df["% nicht ausreichend"] = (df["nicht ausreichend"] / df["Teilnehmer"]) * 100

    amount_of_semesters = range(len(df["Semester"]))
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(16, 12))

    # Stacked bar chart
    categories = ["sehr gut", "gut", "befriedigend", "ausreichend", "nicht ausreichend"]
    df.set_index("Semester")[categories].plot(kind="bar", stacked=True, ax=ax1)
    ax1.set_title(f"Notenverteilung im Modul '{data['Name']}' ({data['Modulnummer']})")
    ax1.set_xlabel("")
    ax1.set_ylabel("Anzahl Teilnehmer")
    ax1.set_xticks(amount_of_semesters)
    ax1.set_xticklabels(df["Semester"], rotation=45, ha="right")
    ax1.legend(title="Note")

    # Percentage line chart
    ax2.plot(amount_of_semesters, df["% nicht ausreichend"], marker="o", linestyle="-")
    ax2.set_title("Prozentualer Anteil 'nicht ausreichend' von allen Teilnehmern")
    ax2.set_xlabel("Semester")
    ax2.set_ylabel("Anteil (%)")
    ax2.set_xticks(amount_of_semesters)
    ax2.set_xticklabels(df["Semester"], rotation=45, ha="right")
    ax2.grid(True, linestyle="--", alpha=0.6)

    output_filename = f"{data['Name']}_{data['Modulnummer']}.png".strip().replace(" ", "_").replace("-", "_").lower()

    plt.tight_layout()
    plt.savefig(output_filename)
    plt.close()


create_combined_diagram(data)




