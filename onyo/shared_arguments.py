shared_arg_message = dict(
    args=('-m', '--message'),
    metavar='MESSAGE',
    action='append',
    type=str,
    help=r"""
        Append the given **MESSAGE** to the commit message.
        If multiple ``--message`` options are given, their values are
        concatenated as separate paragraphs.
    """
)

shared_arg_no_auto_message = dict(
    args=('--no-auto-message',),
    action='store_true',
    help=r"""
        Do not use auto-generated commit message subject.
        This does not disable the inventory operations record
        at the end of a commit message.
        If there's also no **MESSAGE** given, the subject line
        will be ``-``.
    """
)
