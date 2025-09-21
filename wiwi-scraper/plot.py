import matplotlib.pyplot as plt
import pandas as pd

from wiwi_models import StudyModuleModel

# Load all StudyModuleModel objects into memory (example for module_number == "31831")
all_study_modules = list(StudyModuleModel.select().where(StudyModuleModel.module_number == "31831").order_by(StudyModuleModel.year.desc()))

data = {
    "Name": "Knowledge Management",
    "Modulnummer": "31831",
    "Semester": [
        "SS 2017", "WS 2017/18", "SS 2018", "WS 2018/19", "SS 2019",
        "WS 2019/20", "SS 2020", "WS 2020/21", "SS 2021", "WS 2021/22",
        "SS 2022", "WS 2022/23", "SS 2023", "WS 2023/24", "SS 2024",
        "WS 2024/25", "SS 2025"
    ],
    "Teilnehmer": [6, 16, 24, 55, 48, 67, 66, 97, 73, 79, 45, 66, 35, 44, 48, 27, 0],
    "sehr gut": [1, 1, 1, 11, 16, 10, 4, 11, 2, 1, 0, 4, 1, 3, 8, 9, 0],
    "gut": [1, 9, 14, 36, 19, 30, 36, 28, 10, 17, 14, 13, 7, 9, 19, 7, 0],
    "befriedigend": [4, 4, 8, 8, 11, 23, 16, 36, 25, 28, 19, 29, 12, 15, 11, 5, 0],
    "ausreichend": [0, 2, 0, 0, 1, 3, 5, 13, 20, 17, 9, 12, 8, 9, 8, 4, 0],
    "nicht ausreichend": [0, 0, 1, 0, 1, 1, 5, 9, 16, 16, 3, 8, 7, 8, 3, 2, 0]
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

    output_filename = f"{data['Name']}_{data['Modulnummer']}.png".strip().replace(" ", "_").lower()

    plt.tight_layout()
    plt.savefig(output_filename)
    plt.close()


create_combined_diagram(data)




