import matplotlib.pyplot as plt
import pandas as pd

# Data from the user
data = {
    "Semester": [
        "SS 2017", "WS 2017/18", "SS 2018", "WS 2018/19", "SS 2019",
        "WS 2019/20", "SS 2020", "WS 2020/21", "SS 2021", "WS 2021/22",
        "SS 2022", "WS 2022/23", "SS 2023", "WS 2023/24", "SS 2024",
        "WS 2024/25", "SS 2025"
    ],
    "Teilnehmer": [6, 16, 24, 55, 48, 67, 66, 97, 73, 79, 45, 66, 35, 44, 48, 27, None],
    "sehr gut": [1, 1, 1, 11, 16, 10, 4, 11, 2, 1, 0, 4, 1, 3, 8, 9, None],
    "gut": [1, 9, 14, 36, 19, 30, 36, 28, 10, 17, 14, 13, 7, 9, 19, 7, None],
    "befriedigend": [4, 4, 8, 8, 11, 23, 16, 36, 25, 28, 19, 29, 12, 15, 11, 5, None],
    "ausreichend": [0, 2, 0, 0, 1, 3, 5, 13, 20, 17, 9, 12, 8, 9, 8, 4, None],
    "nicht ausreichend": [0, 0, 1, 0, 1, 1, 5, 9, 16, 16, 3, 8, 7, 8, 3, 2, None]
}


def get_grade_distribution_diagram(data):
    # Create DataFrame
    df = pd.DataFrame(data)

    # Plot stacked bar chart
    plt.figure(figsize=(14, 8))
    categories = ["sehr gut", "gut", "befriedigend", "ausreichend", "nicht ausreichend"]
    ax1 = df.set_index("Semester")[categories].plot(kind="bar", stacked=True, figsize=(16,8))

    plt.title("Notenverteilung im Modul 'Knowledge Management' (31831)")
    plt.xlabel("Semester")
    plt.ylabel("Anzahl Studierender")
    plt.xticks(rotation=45, ha="right")
    plt.legend(title="Bewertung")
    plt.tight_layout()
    plt.savefig("notenverteilung_knowledge_management.png")
    plt.close()


def get_failed_students_diagram(data):
    # Create DataFrame
    df = pd.DataFrame(data)

    # Calculate percentage of "nicht ausreichend" relative to total participants
    df["% nicht ausreichend"] = (df["nicht ausreichend"] / df["Teilnehmer"]) * 100

    # Plot percentage trend
    plt.figure(figsize=(12,6))
    plt.plot(df["Semester"], df["% nicht ausreichend"], marker="o", linestyle="-")

    plt.title("Prozentualer Anteil 'nicht ausreichend' an allen Teilnehmern")
    plt.xlabel("Semester")
    plt.ylabel("Anteil (%)")
    plt.xticks(rotation=45, ha="right")
    plt.grid(True, linestyle="--", alpha=0.6)
    plt.tight_layout()
    plt.savefig("prozent_nicht_ausreichend.png")
    plt.close()


get_grade_distribution_diagram(data)
get_failed_students_diagram(data)




