from unittest.mock import patch, MagicMock
import query_volunteers


@patch("sqlite3.connect")
def test_query_volunteers_success(mock_connect):
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_conn.cursor.return_value = mock_cursor
    mock_cursor.fetchone.side_effect = [
        (1,),
        ("email1@example.com",),
        ("email2@example.com",),
    ]
    mock_cursor.fetchall.return_value = [
        ("email1@example.com",),
        ("email2@example.com",),
    ]
    mock_connect.return_value.__enter__.return_value = mock_conn

    query_volunteers.main()  # Извиква функцията main()


@patch("sqlite3.connect")
def test_query_volunteers_no_table(mock_connect):
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_conn.cursor.return_value = mock_cursor
    mock_cursor.fetchone.return_value = None  # Няма таблица
    mock_connect.return_value.__enter__.return_value = mock_conn

    query_volunteers.main()  # Очаква се print за липсваща таблица
