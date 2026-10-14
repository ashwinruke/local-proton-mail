from pmail.clean import clean_body, strip_tracking


def test_html_becomes_plain_text_with_links_kept():
    html = """
    <html><head><style>p{color:red}</style></head><body>
    <table><tr><td><h1>Your order</h1></td></tr>
    <tr><td><p>Hi <b>Alex</b>, track it <a href="https://shop.example/track?id=7&utm_source=email">here</a>.</p>
    <img src="https://shop.example/pixel.gif"></td></tr></table>
    </body></html>"""
    text = clean_body(None, html)
    assert "Your order" in text
    assert "Hi Alex, track it here (https://shop.example/track?id=7)." in text
    for junk in ("<", "#", "**", "pixel.gif", "utm_source", "color:red", "|"):
        assert junk not in text


def test_link_whose_text_is_its_url_is_written_once():
    text = clean_body(None, '<a href="https://example.com/">https://example.com/</a>')
    assert text == "https://example.com/"


def test_invisible_preview_padding_is_removed():
    text = clean_body(None, "<p>Use this link͏ ͏ ­​ to sign in</p>")
    assert text == "Use this link to sign in"


def test_quoted_reply_is_cut():
    plain = "Sounds good, see you then.\n\nOn Tue, Oct 14, 2026 at 9:00 AM Sam <sam@example.com> wrote:\n> Lunch Friday?\n> Sam"
    assert clean_body(plain, None) == "Sounds good, see you then."


def test_proton_original_message_block_is_cut():
    plain = "Thanks!\n\n------- Original Message -------\nOn Monday, Oct 13th, 2026 at 5:00 PM, Sam wrote:\n\n> Here you go"
    assert clean_body(plain, None) == "Thanks!"


def test_outlook_style_quote_is_cut():
    plain = "Approved.\n\nFrom: Sam Lee <sam@example.com>\nSent: Monday, October 13, 2026 5:00 PM\nSubject: Budget"
    assert clean_body(plain, None) == "Approved."


def test_message_that_is_only_a_quote_is_kept():
    plain = "On Tue, Oct 14, 2026 Sam wrote:\n> Lunch Friday?"
    assert "Lunch Friday?" in clean_body(plain, None)


def test_signature_and_signoff_are_removed():
    plain = "See attached.\n\n-- \nAlex Doe\nCEO, Example Co\n\nSent with Proton Mail secure email."
    assert clean_body(plain, None) == "See attached."


def test_inline_reply_quotes_in_the_middle_are_kept():
    plain = "> Can you do Friday?\nYes, Friday works.\n> And the budget?\nApproved."
    assert clean_body(plain, None) == plain


def test_plain_text_urls_lose_tracking_params():
    assert clean_body("Read https://news.example/a?utm_medium=x&page=2 now", None) == "Read https://news.example/a?page=2 now"


def test_strip_tracking_leaves_clean_urls_alone():
    url = "https://example.com/path?q=1#frag"
    assert strip_tracking(url) == url


def test_links_wrapped_around_links_are_flattened():
    html = '<a href="https://jobs.example/1"><div><a href="https://co.example">Acme</a></div><div>Remote</div></a>'
    text = clean_body(None, html)
    assert "](" not in text and "[" not in text
    assert "Acme (https://co.example)" in text
    assert "https://jobs.example/1" in text


def test_bold_markers_in_plain_text_are_removed():
    assert clean_body("Your **new** score", None) == "Your new score"
