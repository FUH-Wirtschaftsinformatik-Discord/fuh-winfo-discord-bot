import matplotlib.pyplot as plt
import pandas as pd
from peewee import Case
import os
from models import ModuleGradeStatistics, ModuleGradeStatisticsGraphic

def get_module_numbers() -> set[str]:
    # Get all unique module numbers from the database
    unique_module_numbers = list(
        ModuleGradeStatistics.select(ModuleGradeStatistics.module_number)
        .distinct()
        .order_by(ModuleGradeStatistics.module_number)
        .tuples()
    )
    unique_module_numbers = set([num[0] for num in unique_module_numbers])
    return unique_module_numbers

def extract_grade_statistics(module_number: str, limit_semesters=20) -> dict:
    if module_number is None or len(module_number.strip()) == 0:
        raise ValueError("Module number is not specified or is empty.")
    if limit_semesters <= 0:
        raise ValueError("Limit of semesters must be greater than zero.")

    # Load all StudyModuleModel objects into memory (example for module_number == "31831")
    # Order by year, then is_summer_semester (1 first), then examination_period with P2 last using peewee.Case
    statistics_by_semester = list(
        ModuleGradeStatistics.select()
        .where(ModuleGradeStatistics.module_number == module_number.strip())
        .order_by(
            ModuleGradeStatistics.year,
            ModuleGradeStatistics.is_summer_semester.asc(),
            Case(None, ((ModuleGradeStatistics.examination_period == "P2", 1),), 0)
        )
    )

    # Limit the number of semesters to the last 'limit_semesters' entries
    limit_statistics_by_semester = statistics_by_semester[(-1*limit_semesters):]

    if len(limit_statistics_by_semester) == 0:
        raise ValueError(f"No data found for module number: {module_number}. Module might not exist (in the database).")

    module_name=limit_statistics_by_semester[0].module_name if len(limit_statistics_by_semester) > 0 else "Unknown"

    semester_labels: list[str] = []
    participant_labels: list[int] = []
    very_good_labels: list[int] = []
    good_labels: list[int] = []
    satisfactory_labels: list[int] = []
    sufficient_labels: list[int] = []
    insufficient_labels: list[int] = []

    checksum=0

    for module in limit_statistics_by_semester:
    
        semester_label=""
        if module.is_summer_semester:
            semester_label = f"SS{module.year}"
        else:
            semester_label = f"WS{module.year-1}/{module.year}"

        semester_labels.append(f"{semester_label} {module.examination_period}")
        participants = module.very_good + module.good + module.satisfactory + module.sufficient + module.insufficient
        participant_labels.append(participants)
        very_good_labels.append(module.very_good)   
        good_labels.append(module.good)
        satisfactory_labels.append(module.satisfactory)
        sufficient_labels.append(module.sufficient)
        insufficient_labels.append(module.insufficient)

        checksum+=participants + module.very_good + module.good + module.satisfactory + module.sufficient + module.insufficient

    data = {
        "Name": module_name,
        "Modulnummer": module_number.strip(),
        "Semester": semester_labels,
        "Teilnehmer": participant_labels,
        "sehr gut": very_good_labels,
        "gut": good_labels,
        "befriedigend": satisfactory_labels,
        "ausreichend": sufficient_labels,
        "nicht ausreichend": insufficient_labels,
        "Checksum": checksum
    }

    return data

def plot_diagram_as_complex_file(data: dict, output_directory='plots') -> str:
    if data is None or len(data) == 0:
        raise ValueError("No data provided for plotting. Data dictionary is empty or None.")

    if output_directory is None or len(output_directory.strip()) == 0:
        raise ValueError("Output directory is not specified or is empty.")

    # prepare file path
    if not os.path.exists(output_directory):
        os.makedirs(output_directory)
    output_filename = os.path.join(output_directory, f"{data['Modulnummer'].strip()}.png".strip().lower())
    full_output_filename = os.path.abspath(output_filename)
    
    # draw combined diagram
    df = pd.DataFrame(data).dropna()

    # Stacked bar chart
    categories = ["sehr gut", "gut", "befriedigend", "ausreichend", "nicht ausreichend"]
    colors = ["#2ecc71","#f1c40f","#3498db","#e67e22","#e74c3c" ]
    
    categories.reverse()
    colors.reverse()

    # Normalize to percentages
    df_percent = df[categories].div(df["Teilnehmer"], axis=0) * 100

    fig, ax = plt.subplots(figsize=(18, 9))

    bottom = None
    for idx, cat in enumerate(categories):
        ax.bar(df["Semester"], df_percent[cat], bottom=bottom, label=cat, color=colors[idx])
        if bottom is None:
            bottom = df_percent[cat].copy()
        else:
            bottom += df_percent[cat]

    # Add percentage labels inside bars
    for i, semester in enumerate(df["Semester"]):
        cumulative = 0
        for idx, cat in enumerate(categories):
            value = df_percent[cat].iloc[i]
            if value > 0:  # only label non-empty sections
                ax.text(
                    i,
                    cumulative + value / 2,
                    f"{value:.0f}%",
                    ha="center",
                    va="center",
                    color="black",
                    fontsize=8
                )
            cumulative += value   


    # Labels and legend
    ax.set_title(f"Notenverteilung im Modul '{data['Name']}' ({data['Modulnummer']})")
    ax.set_xlabel("Semester")
    ax.set_ylabel("Prozent der Studierenden")
    ax.set_xticks(range(len(df["Semester"])))
    ax.set_xticklabels(df["Semester"], rotation=45, ha="right")
    ax.set_ylim(0, 110)  # y-axis scale higher than 100%
    ax.legend(title="Bewertung", bbox_to_anchor=(1.05, 1), loc="upper left", fontsize=8)

    plt.tight_layout()
    plt.savefig(full_output_filename, dpi=300)
    plt.close()

    return full_output_filename

def plot_all_statistics():
    print("Starting plot generation...")

    plotted = {}

    for module_number in get_module_numbers():
        print(f"Creating plots for module number: {module_number}")

        statistics = extract_grade_statistics(module_number)
        full_file_path = plot_diagram_as_complex_file(statistics)

        plotted[module_number] = {
            "Path": full_file_path,
        }

        # Store only the filename (not full path)
        file_name = os.path.basename(full_file_path)
        graphic_entry, created = ModuleGradeStatisticsGraphic.get_or_create(
            module_number=module_number,
            defaults={
                "module_number": module_number,
                "path": file_name
            }
        )
        if not created:
            # Update existing entry
            graphic_entry.module_number = module_number
            graphic_entry.path = file_name
            graphic_entry.save()

        print(f"Created/Updated ModuleGradeStatisticsGraphic for module number: {module_number} at {file_name}")

    print("Plot generation completed.")

plot_all_statistics()