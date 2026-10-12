from app.services.document_view_service import document_blocks

def test_blank_table_row_and_headings_survive_editable_text_parser():
    blocks = document_blocks("5. Содержание дисциплины\n№\tТема\tСодержание\n1\tТема A\tОписание\n\nЛист актуализации\nДата\tПодпись\n\t")
    assert blocks[0]["kind"] == "heading"
    assert blocks[1]["headers"] == ["№", "Тема", "Содержание"]
    assert blocks[1]["rows"] == [["1", "Тема A", "Описание"]]
    assert blocks[-1]["rows"] == [["", ""]]
