import asyncio
from matplotlib.axes import Axes
import matplotlib.pyplot as plt
import pandas as pd
from peewee import Case
import os
from models import ModuleGradeStatistics, ModuleGradeStatisticsGraphic
import logging

# Configure logger
logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
logger = logging.getLogger(__name__)

CHART_CATEGORIES = ["nicht ausreichend", "ausreichend", "befriedigend", "gut", "sehr gut"]
CHART_COLORS = ["#e74c3c", "#e67e22", "#3498db", "#f1c40f", "#2ecc71"]   

async def get_module_numbers() -> set[int]:
    """
    Get all unique module numbers from the database.
    Returns a set of integers.
    """
    unique_module_numbers = list(
        ModuleGradeStatistics.select(ModuleGradeStatistics.module_number)
        .distinct()
        .order_by(ModuleGradeStatistics.module_number)
        .tuples()
    )

    sorted_module_numbers = [num[0] for num in unique_module_numbers]
    sorted_module_numbers.sort()

    return set(sorted_module_numbers)


async def extract_grade_statistics(module_number: int, limit_semesters=20) -> dict:
    """
    Extract grade statistics for a module from the database.
    Returns a dictionary with all relevant data for plotting.
    """
    if module_number is None or module_number <= 0:
        raise ValueError("Module number is not specified or is empty.")
    if limit_semesters <= 0:
        raise ValueError("Limit of semesters must be greater than zero.")

    # Query all statistics for the module, ordered by year and semester
    statistics_by_semester = list(
        ModuleGradeStatistics.select()
        .where(ModuleGradeStatistics.module_number == module_number)
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

    module_name = limit_statistics_by_semester[0].module_name.strip()

    # Helper to build lists for plotting
    def build_labels(modules):
        """
        Build lists for plotting from a list of module statistics.
        Returns all required lists and a checksum.
        """
        semester_labels = []
        participant_labels = []
        very_good_labels = []
        good_labels = []
        satisfactory_labels = []
        sufficient_labels = []
        insufficient_labels = []
        checksum = 0
        for module in modules:
            # Build semester label
            if module.is_summer_semester:
                semester_label = f"SS{module.year}"
            else:
                semester_label = f"WS{module.year-1}/{module.year}"
            semester_labels.append(f"{semester_label} {module.examination_period}")
            # Calculate participants
            participants = module.very_good + module.good + module.satisfactory + module.sufficient + module.insufficient
            participant_labels.append(participants)
            # Add grades
            very_good_labels.append(module.very_good)
            good_labels.append(module.good)
            satisfactory_labels.append(module.satisfactory)
            sufficient_labels.append(module.sufficient)
            insufficient_labels.append(module.insufficient)
            # Update checksum
            checksum += participants + module.very_good + module.good + module.satisfactory + module.sufficient + module.insufficient
        return semester_labels, participant_labels, very_good_labels, good_labels, satisfactory_labels, sufficient_labels, insufficient_labels, checksum

    semester_labels, participant_labels, very_good_labels, good_labels, satisfactory_labels, sufficient_labels, insufficient_labels, checksum = build_labels(limit_statistics_by_semester)

    # Build data dictionary for plotting
    data = {
        "Name": module_name,
        "Modulnummer": module_number,
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

def draw_stacked_bars(ax: Axes, df_percent: pd.DataFrame, semester_df: pd.DataFrame, categories: list, colors: list):
    """
    Draw stacked bars for each grade category.
    """
    bottom = None
    for idx, category in enumerate(categories):
        ax.bar(semester_df, df_percent[category], bottom=bottom, label=category, color=colors[idx])
        if bottom is None:
            bottom = df_percent[category].copy()
        else:
            bottom += df_percent[category]

def add_percentage_labels(ax: Axes, df_percent: pd.DataFrame, df_semester: pd.DataFrame, categories: list):
    """
    Add percentage labels inside each bar segment.
    """
    for i, semester in enumerate(df_semester):
        cumulative = 0
        for idx, category in enumerate(categories):
            value = df_percent[category].iloc[i]
            if value > 0:
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

async def plot_diagram_as_complex_file(data: dict, output_directory='plots') -> str:
    """
    Plot a stacked bar chart of grade statistics as percentages and save as PNG file.
    Returns the full path to the saved file.
    """
    if data is None or len(data) == 0:
        raise ValueError("No data provided for plotting. Data dictionary is empty or None.")
    if output_directory is None or len(output_directory.strip()) == 0:
        raise ValueError("Output directory is not specified or is empty.")
    # Prepare file path
    if not os.path.exists(output_directory):
        os.makedirs(output_directory)
    output_filename = os.path.join(output_directory, f"{data['Modulnummer']}.png")
    full_output_filename = os.path.abspath(output_filename)

    # Prepare DataFrame
    df = pd.DataFrame(data).dropna()

    # Normalize to percentages
    df_percent = df[CHART_CATEGORIES].div(df["Teilnehmer"], axis=0) * 100
    fig, ax = plt.subplots(figsize=(18, 9))

    # Draw stacked bars
    draw_stacked_bars(ax, df_percent,df["Semester"], CHART_CATEGORIES, CHART_COLORS)

    # Add percentage labels inside bars
    add_percentage_labels(ax, df_percent, df["Semester"], CHART_CATEGORIES)
    # Labels and legend
    ax.set_title(f"Notenverteilung im Modul '{data['Name']} ({data['Modulnummer']})'")
    ax.set_xlabel("Semester")
    ax.set_ylabel("Prozent der Studierenden")
    ax.set_xticks(range(len(df["Semester"])))
    ax.set_xticklabels(df["Semester"], rotation=45, ha="right")
    ax.set_ylim(0, 110)  # y-axis scale higher than 100%
    ax.legend(title="Bewertung", bbox_to_anchor=(1.05, 1), loc="upper left", fontsize=10)
    
    # Save plot to file
    plt.tight_layout()
    plt.savefig(full_output_filename, dpi=300)
    plt.close()

    return full_output_filename


async def plot_all_statistics():
    """
    Generate and save plots for all modules in the database.
    Updates/creates ModuleGradeStatisticsGraphic entries for each module.
    """
    logger.info("Starting plot generation...")
    
    module_numbers = await get_module_numbers()

    for module_number in module_numbers:
        logger.info(f"Creating plots for module number: {module_number}")
        statistics = await extract_grade_statistics(module_number)
        full_file_path = await plot_diagram_as_complex_file(statistics)
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
        logger.info(f"Created/Updated ModuleGradeStatisticsGraphic for module number: {module_number} at {file_name}")
    
    logger.info("Plot generation completed.")

if __name__ == "__main__":
    asyncio.run(plot_all_statistics())