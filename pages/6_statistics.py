import logging

import altair as alt
import pandas as pd
import streamlit as st

from src.logger_config import setup_logger
from src.search_service import search_songs
from src.statistics_service import (
    get_database_summary,
    get_song_statistics,
    get_most_frequent_words,
    get_rarest_words,
    get_word_length_distribution,
    get_words_per_stanza
)

setup_logger()

logger = logging.getLogger(__name__)


def get_song_options() -> dict[str, int]:
    """
    Retrieves all songs and builds options for the song selector.
    :return: A dictionary mapping a unique label with album and ID to its song ID.
    """
    logger.info("Fetching songs for statistics page")

    try:
        songs = search_songs()
        options = {
            f"{title} — {artist} — {album or 'No album'} (ID: {song_id})": song_id
            for (song_id, title, artist, album, publication_year, upload_date) in songs
        }

        logger.info(f'Fetched {len(options)} songs for statistics selector')
        return options

    except Exception as e:
        logger.error(f"Failed to fetch songs for statistics selector due to {e}")
        raise


def render_database_summary() -> None:
    """
    Displays general statistics for the entire database.
    :return: None.
    """
    logger.info("Rendering database summary statistics")

    try:
        summary = get_database_summary()
        st.subheader("Database Summary")
        col1, col2, col3 = st.columns(3)

        with col1:
            st.metric(
                "Songs",
                summary["song_count"]
            )

        with col2:
            st.metric(
                "Total Words",
                summary["total_words"]
            )

        with col3:
            st.metric(
                "Unique Words",
                summary["unique_words"]
            )

        col4, col5 = st.columns(2)

        with col4:
            st.metric(
                "Average Word Length",
                summary["average_word_length"]
            )

        with col5:
            st.metric(
                "Average Words per Line",
                summary["average_words_per_line"]
            )

        logger.info("Database summary rendered successfully")

    except Exception as e:
        logger.error(f"Failed to render database summary due to {e}")
        st.error("Could not load database summary statistics.")


def render_song_summary(song_id: int) -> None:
    """
    Displays summary statistics for a specific song.
    :param song_id: The database ID of the selected song.
    :return: None.
    """
    logger.info(f'Rendering summary statistics for song id {song_id}')

    try:
        statistics = get_song_statistics(song_id=song_id)

        if statistics is None:
            logger.warning(f'No statistics found for song id {song_id}')
            st.warning("The selected song could not be found.")
            return

        st.subheader(f"Song Summary — {statistics['title']}")
        col1, col2, col3 = st.columns(3)

        with col1:
            st.metric("Stanzas", statistics["stanza_count"])

        with col2:
            st.metric("Lines",statistics["line_count"])

        with col3:
            st.metric("Words", statistics["word_count"])

        col4, col5 = st.columns(2)

        with col4:
            st.metric("Unique Words", statistics["unique_word_count"])

        with col5:
            st.metric("Average Word Length", statistics["average_word_length"])

        logger.info(f'Song summary rendered successfully for song id {song_id}')

    except Exception as e:
        logger.error(f'Failed to render statistics for song id {song_id} due to {e}')
        st.error("Could not load statistics for the selected song.")


def render_frequency_tables(song_id: int | None) -> None:
    """
    Displays the most frequent and rarest words.
    :param song_id: Optional song ID. If None, statistics are calculated for the entire database.
    :return: None.
    """
    logger.info(f'Rendering frequency tables for song id {song_id}')

    try:
        frequent_words = get_most_frequent_words(limit=10, song_id=song_id)
        rare_words = get_rarest_words(limit=10, song_id=song_id)
        col1, col2 = st.columns(2)

        with col1:
            st.subheader("Most Frequent Words")
            frequent_rows = [{"Word": word, "Occurrences": count} for word, count in frequent_words]
            st.dataframe(frequent_rows, use_container_width=True, hide_index=True)

        with col2:
            st.subheader("Rarest Words")
            rare_rows = [{"Word": word, "Occurrences": count} for word, count in rare_words]
            st.dataframe(rare_rows, use_container_width=True, hide_index=True)

        logger.info("Frequency tables rendered successfully")

    except Exception as e:
        logger.error(f"Failed to render frequency tables due to {e}")
        st.error("Could not load word frequency statistics.")


def render_frequency_chart(song_id: int | None) -> None:
    """
    Displays a bar chart of the most frequent words.
    :param song_id: Optional song ID. If None, statistics are calculated for the entire database.
    :return: None.
    """
    logger.info(f'Rendering word frequency chart for song id {song_id}')

    try:
        frequent_words = get_most_frequent_words(limit=10, song_id=song_id)

        if not frequent_words:
            logger.info("No frequency data available for chart")
            st.info("No word frequency data is available.")
            return

        dataframe = pd.DataFrame(frequent_words, columns=["Word", "Occurrences"])
        dataframe = dataframe.set_index("Word")
        st.subheader("Most Frequent Words Chart")
        st.bar_chart(dataframe["Occurrences"])

        logger.info("Word frequency chart rendered successfully")

    except Exception as e:
        logger.error(f"Failed to render word frequency chart due to {e}")
        st.error("Could not render the word frequency chart.")


def render_word_length_distribution(song_id: int | None) -> None:
    """
    Displays the distribution of word lengths.
    :param song_id: Optional song ID. If None, statistics are calculated for the entire database.
    :return: None.
    """
    logger.info(f'Rendering word length distribution for song id {song_id}')

    try:
        distribution = get_word_length_distribution(song_id=song_id)

        if not distribution:
            logger.info("No word length distribution data available")
            st.info("No word length data is available.")
            return

        dataframe = pd.DataFrame(distribution, columns=["Word Length", "Occurrences"])
        dataframe = dataframe.set_index("Word Length")
        st.subheader("Word Length Distribution")
        st.bar_chart(dataframe["Occurrences"])

        logger.info("Word length distribution rendered successfully")

    except Exception as e:
        logger.error(f"Failed to render word length distribution due to {e}")
        st.error("Could not render the word length distribution.")


def render_words_per_stanza(song_id: int) -> None:
    """
    Displays the number of words in each stanza of a song.
    :param song_id: The database ID of the selected song.
    :return: None.
    """
    logger.info(f'Rendering words per stanza for song id {song_id}')

    try:
        stanza_statistics = get_words_per_stanza(song_id=song_id)

        if not stanza_statistics:
            logger.info(f'No stanza statistics found for song id {song_id}')
            st.info("No stanza statistics are available.")
            return

        dataframe = pd.DataFrame(stanza_statistics, columns=["Stanza", "Word Count"])
        dataframe = dataframe.set_index("Stanza")
        st.subheader("Words per Stanza")
        st.bar_chart(dataframe["Word Count"])
        logger.info(f'Words-per-stanza chart rendered successfully for song id {song_id}')

    except Exception as e:
        logger.error(f'Failed to render words per stanza for song id {song_id} due to {e}')
        st.error("Could not render stanza statistics.")


def main() -> None:
    """
    Renders the Statistics page.
    The page allows users to view statistics for the entire database or for a specific song.
    It displays summary metrics, frequency tables, and charts for word frequency, word length distribution,
    and words per stanza.
    :return: None.
    """
    logger.info("Rendering statistics page")
    st.title("Statistics")

    st.write("Explore statistics about the songs, words, word frequencies, and text structure.")

    try:
        song_options = get_song_options()

    except Exception as e:
        logger.error(f"Failed to load songs for statistics page due to {e}")
        st.error("Could not load the available songs.")
        return

    filter_options: dict[str, int | None] = {"Entire Database": None, **song_options}
    selected_label = st.selectbox("Statistics Scope", options=list(filter_options.keys()))
    selected_song_id = filter_options[selected_label]

    logger.info(f'Statistics scope selected: {selected_label}')

    # Summary section
    if selected_song_id is None:
        render_database_summary()

    else:
        render_song_summary(song_id=selected_song_id)

    st.markdown("---")

    # Frequency tables
    render_frequency_tables(song_id=selected_song_id)

    st.markdown("---")

    # Most frequent words chart
    logger.info(f'Rendering most frequent words chart for song id {selected_song_id}')

    try:
        frequent_words = get_most_frequent_words(limit=10, song_id=selected_song_id)

        if frequent_words:
            frequent_dataframe = pd.DataFrame(frequent_words, columns=["Word", "Occurrences"])
            st.subheader("Most Frequent Words Chart")

            frequency_chart = (
                alt.Chart(frequent_dataframe)
                .mark_bar()
                .encode(
                    x=alt.X(
                        "Word:N",
                        sort="-y",
                        axis=alt.Axis(
                            labelAngle=0,
                            title="Word"
                        )
                    ),
                    y=alt.Y(
                        "Occurrences:Q",
                        title="Occurrences"
                    ),
                    tooltip=[
                        alt.Tooltip(
                            "Word:N",
                            title="Word"
                        ),
                        alt.Tooltip(
                            "Occurrences:Q",
                            title="Occurrences"
                        )
                    ]
                )
            )

            st.altair_chart(frequency_chart, use_container_width=True)

            logger.info("Most frequent words chart rendered successfully")

        else:
            logger.info("No frequency data available for chart")
            st.info("No word frequency data is available.")

    except Exception as e:
        logger.error(f"Failed to render most frequent words chart due to {e}")
        st.error("Could not render the word frequency chart.")

    st.markdown("---")

    # Word length distribution
    logger.info(f'Rendering word length distribution for song id {selected_song_id}')

    try:
        distribution = get_word_length_distribution(song_id=selected_song_id)

        if distribution:
            distribution_dataframe = pd.DataFrame(distribution, columns=["Word Length", "Occurrences"])
            st.subheader("Word Length Distribution")

            length_chart = (
                alt.Chart(distribution_dataframe)
                .mark_bar()
                .encode(
                    x=alt.X(
                        "Word Length:O",
                        axis=alt.Axis(
                            labelAngle=0,
                            title="Word Length"
                        ),
                    ),
                    y=alt.Y(
                        "Occurrences:Q",
                        title="Occurrences"
                    ),
                    tooltip=[
                        alt.Tooltip(
                            "Word Length:O",
                            title="Word Length"
                        ),
                        alt.Tooltip(
                            "Occurrences:Q",
                            title="Occurrences"
                        )
                    ]
                )
            )

            st.altair_chart(length_chart, use_container_width=True)
            logger.info("Word length distribution rendered successfully")

        else:
            logger.info("No word length distribution data available")
            st.info("No word length data is available.")

    except Exception as e:
        logger.error(f"Failed to render word length distribution due to {e}")
        st.error("Could not render the word length distribution.")

    # Words per stanza - only for a specific song
    if selected_song_id is not None:
        st.markdown("---")
        logger.info(f'Rendering words per stanza for song id {selected_song_id}')

        try:
            stanza_statistics = get_words_per_stanza(song_id=selected_song_id)

            if stanza_statistics:
                stanza_dataframe = pd.DataFrame(stanza_statistics, columns=["Stanza", "Word Count"])
                st.subheader("Words per Stanza")

                stanza_chart = (
                    alt.Chart(stanza_dataframe)
                    .mark_bar()
                    .encode(
                        x=alt.X(
                            "Stanza:O",
                            axis=alt.Axis(
                                labelAngle=0,
                                title="Stanza"
                            ),
                        ),
                        y=alt.Y(
                            "Word Count:Q",
                            title="Word Count"
                        ),
                        tooltip=[
                            alt.Tooltip(
                                "Stanza:O",
                                title="Stanza"
                            ),
                            alt.Tooltip(
                                "Word Count:Q",
                                title="Word Count"
                            )
                        ]
                    )
                )

                st.altair_chart(stanza_chart, use_container_width=True)
                logger.info("Words per stanza chart rendered successfully")

            else:
                logger.info(f'No stanza statistics available for song id {selected_song_id}')
                st.info("No stanza statistics are available.")

        except Exception as e:
            logger.error(f"Failed to render words per stanza for song id {selected_song_id} due to {e}")
            st.error("Could not render stanza statistics.")

    logger.info("Statistics page rendered successfully")


if __name__ == "__main__":
    main()
