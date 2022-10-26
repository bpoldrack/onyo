import argparse
import logging
import os
import sys
import textwrap

from onyo import commands
from onyo._version import __version__

logging.basicConfig()
log = logging.getLogger('onyo')
log.setLevel(logging.INFO)


# This class enables e.g. onyo set to receive a dictionary of key=value
class StoreDictKeyPair(argparse.Action):
    def __init__(self, option_strings, dest, nargs=None, **kwargs):
        self._nargs = nargs
        super(StoreDictKeyPair, self).__init__(option_strings, dest, nargs=nargs, **kwargs)

    def __call__(self, parser, namespace, values, option_string=None):
        my_dict = {}
        for pair in parse_key_values(values):
            k = pair[0]
            v = pair[1]
            my_dict[k] = v
        setattr(namespace, self.dest, my_dict)


# credit: https://stackoverflow.com/a/13429281
class SubcommandHelpFormatter(argparse.RawDescriptionHelpFormatter):
    def _format_action(self, action):
        parts = super()._format_action(action)

        # strip the first line (metavar) of the subcommands section
        if action.nargs == argparse.PARSER:
            parts = parts.split("\n", 1)[1]

        return parts

    def _fill_text(self, text, width, indent):
        """
        This is a very, very naive approach to stripping rst syntax from
        docstrings. Sadly, docutils does not have a plain-text writer. That
        would be the ideal solution.
        """
        text = super()._fill_text(text, width, indent)

        # `` -> `
        text = text.replace('``', '`')
        # remove escapes of characters; everything is literal here
        text = text.replace('\\', '')

        return text


def parse_key_values(values):
    results = []
    rest_str = values
    key = ""
    value = ""
    while True:
        if len(rest_str) <= 0:
            break
        next_equal = rest_str.find('=')
        # this happens when `onyo set a=5,b` is called and value is missing
        if next_equal == -1:
            log.error("No value after \"" + rest_str + "\". (Equal sign expected)")
            sys.exit(1)
        # find key:
        key = rest_str[0:next_equal]
        # go behind equal sign
        rest_str = rest_str[next_equal + 1:]
        # --- find value ---:
        # if value starts with quote (then go to next quote, ignore commas until
        # then)
        if rest_str[0] == '"':
            # next_quote ignores the first quote and looks for the next one
            next_quote = rest_str[1:].find('"')
            # next comma is then behind the quote
            next_comma = rest_str[1 + next_quote:].find(',')
            # if no other comma found, assume end of input
            if next_comma == -1:
                # if end reached and in quotes, ignore the leading and ending
                # quote for string
                value = rest_str[1:-1]
                rest_str = ""
            # take value until the next comma, rest_str starts then from behind
            # the comma (with the next key/value pair)
            else:
                # the value to set beginns with/after quote and goes to the
                # first comma after the next quote (e.g. it should skip the
                # quoted comma in "12 , 12")
                value = rest_str[1: next_quote + next_comma]
                # rest string should be after the next comma (outside/after the
                # next quote), and then go +2 to be first after the quote, and
                # second after the following comma
                rest_str = rest_str[next_quote + next_comma + 2:]
        # if value does not start with quote, just go to next comma
        else:
            # go to the next comma
            next_comma = rest_str.find(',')
            # if there is no next comma, assume end of input
            if next_comma == -1:
                value = rest_str
                rest_str = ""
            # if there is a comma, the value will end behind it and the rest_str
            # should follow with the next key/value pair
            else:
                value = rest_str[:next_comma]
                rest_str = rest_str[next_comma + 1:]
            # if the given values are int/float (and not in quotes), they
            # should be treated as such
            try:
                value = int(value)
            except ValueError:
                try:
                    value = float(value)
                except ValueError:
                    pass
        # add result
        results.append([key, value])
    # return key value pairs
    return results


def directory(string):
    """
    A no-op type-check for ArgParse. Used to hint for shell tab-completion.
    """
    return string


def file(string):
    """
    A no-op type-check for ArgParse. Used to hint for shell tab-completion.
    """
    return string


def git_config(string):
    """
    A no-op type-check for ArgParse. Used to hint for shell tab-completion.
    """
    return string


def path(string):
    """
    A no-op type-check for ArgParse. Used to hint for shell tab-completion.
    """
    return string


def template(string):
    """
    A no-op type-check for ArgParse. Used to hint for shell tab-completion.
    """
    return string


def setup_parser():
    parser = argparse.ArgumentParser(
        description='A text-based inventory system backed by git.',
        formatter_class=SubcommandHelpFormatter
    )
    parser.add_argument(
        '-C',
        '--onyopath',
        metavar='DIR',
        required=False,
        default=os.getcwd(),
        type=directory,
        help='run as if onyo was started in DIR'
    )
    parser.add_argument(
        '-d',
        '--debug',
        required=False,
        default=False,
        action='store_true',
        help='enable debug logging'
    )
    parser.add_argument(
        '--version',
        action='version',
        version='%(prog)s {version}'.format(version=__version__),
        help="print onyo's version and exit"
    )
    # subcommands
    subcmds = parser.add_subparsers(
        title="commands"
    )
    subcmds.metavar = '<command>'
    #
    # subcommand cat
    #
    cmd_cat = subcmds.add_parser(
        'cat',
        description=textwrap.dedent(commands.cat.__doc__),
        formatter_class=SubcommandHelpFormatter,
        help='print the contents of an asset'
    )
    cmd_cat.set_defaults(run=commands.cat)
    cmd_cat.add_argument(
        'asset',
        metavar='ASSET',
        nargs='+',
        type=file,
        help='asset(s) to print'
    )
    #
    # subcommand "config"
    #
    cmd_config = subcmds.add_parser(
        'config',
        description=textwrap.dedent(commands.config.__doc__),
        formatter_class=SubcommandHelpFormatter,
        help='set, query, and unset Onyo repository configuration options'
    )
    cmd_config.set_defaults(run=commands.config)
    cmd_config.add_argument(
        'git_config_args',
        metavar='ARGS',
        nargs='+',
        type=git_config,
        help='arguments to set config options in .onyo/config'
    )
    #
    # subcommand "edit"
    #
    cmd_edit = subcmds.add_parser(
        'edit',
        description=textwrap.dedent(commands.edit.__doc__),
        formatter_class=SubcommandHelpFormatter,
        help='open asset with a text editor'
    )
    cmd_edit.set_defaults(run=commands.edit)
    cmd_edit.add_argument(
        'asset',
        metavar='ASSET',
        nargs='+',
        type=file,
        help='asset(s) to edit'
    )
    #
    # subcommand "fsck"
    #
    cmd_fsck = subcmds.add_parser(
        'fsck',
        description=textwrap.dedent(commands.fsck.__doc__),
        formatter_class=SubcommandHelpFormatter,
        help='verify the integrity and validity of an onyo repository and its contents'
    )
    cmd_fsck.set_defaults(run=commands.fsck)
    #
    # subcommand "history"
    #
    cmd_history = subcmds.add_parser(
        'history',
        description=textwrap.dedent(commands.history.__doc__),
        formatter_class=SubcommandHelpFormatter,
        help='show the history of an asset or directory'
    )
    cmd_history.set_defaults(run=commands.history)
    cmd_history.add_argument(
        '-I', '--non-interactive',
        dest='interactive',
        required=False,
        default=True,
        action='store_false',
        help='print the git log instead of opening an interactive tig session'
    )
    cmd_history.add_argument(
        'path',
        metavar='PATH',
        nargs='?',
        type=path,
        help='asset or directory to show the history of'
    )
    #
    # subcommand "init"
    #
    cmd_init = subcmds.add_parser(
        'init',
        description=textwrap.dedent(commands.init.__doc__),
        formatter_class=SubcommandHelpFormatter,
        help='initialize an onyo repository'
    )
    cmd_init.set_defaults(run=commands.init)
    cmd_init.add_argument(
        'directory',
        metavar='DIR',
        nargs='?',
        type=directory,
        help='initialize DIR as an onyo repository'
    )
    #
    # subcommand "mkdir"
    #
    cmd_mkdir = subcmds.add_parser(
        'mkdir',
        description=textwrap.dedent(commands.mkdir.__doc__),
        formatter_class=SubcommandHelpFormatter,
        help='create a directory (with git anchor)'
    )
    cmd_mkdir.set_defaults(run=commands.mkdir)
    cmd_mkdir.add_argument(
        'directory',
        metavar='DIR',
        nargs='+',
        type=directory,
        help='directory to create'
    )
    #
    # subcommand "mv"
    #
    cmd_mv = subcmds.add_parser(
        'mv',
        description=textwrap.dedent(commands.mv.__doc__),
        formatter_class=SubcommandHelpFormatter,
        help='move an asset'
    )
    cmd_mv.set_defaults(run=commands.mv)
    cmd_mv.add_argument(
        '-q', '--quiet',
        required=False,
        default=False,
        action='store_true',
        help='silence messages to stdout (requires the --yes flag)'
    )
    cmd_mv.add_argument(
        '-y', '--yes',
        required=False,
        default=False,
        action='store_true',
        help='respond "yes" to any prompts'
    )
    cmd_mv.add_argument(
        'source',
        metavar='SOURCE',
        nargs='+',
        type=path,
        help='source ...'
    )
    cmd_mv.add_argument(
        'destination',
        metavar='DEST',
        type=path,
        help='destination'
    )
    #
    # subcommand "new"
    #
    cmd_new = subcmds.add_parser(
        'new',
        description=textwrap.dedent(commands.new.__doc__),
        formatter_class=SubcommandHelpFormatter,
        help='create a new asset'
    )
    cmd_new.set_defaults(run=commands.new)
    cmd_new.add_argument(
        '-I', '--non-interactive',
        dest='interactive',
        required=False,
        default=True,
        action='store_false',
        help='do not prompt or open the editor; values must be piped in (e.g. echo "<type>\\n<make>\\n<model>\\n<serial>" | onyo new -I shelf/)'
    )
    cmd_new.add_argument(
        '-t', '--template',
        metavar='TEMPLATE',
        required=False,
        default=None,
        type=template,
        help='the template to seed the new asset'
    )
    cmd_new.add_argument(
        'directory',
        metavar='DIR',
        type=directory,
        help='add a new asset to DIR'
    )
    #
    # subcommand "rm"
    #
    cmd_rm = subcmds.add_parser(
        'rm',
        description=textwrap.dedent(commands.rm.__doc__),
        formatter_class=SubcommandHelpFormatter,
        help='delete asset(s) and directories'
    )
    cmd_rm.set_defaults(run=commands.rm)
    cmd_rm.add_argument(
        '-q', '--quiet',
        required=False,
        default=False,
        action='store_true',
        help='silence messages to stdout (requires the --yes flag)'
    )
    cmd_rm.add_argument(
        '-y', '--yes',
        required=False,
        default=False,
        action='store_true',
        help='respond "yes" to any prompts'
    )
    cmd_rm.add_argument(
        'path',
        metavar='PATH',
        nargs='+',
        type=path,
        help='assets or directories to delete'
    )
    #
    # subcommand "set"
    #
    cmd_set = subcmds.add_parser(
        'set',
        description=textwrap.dedent(commands.set.__doc__),
        formatter_class=SubcommandHelpFormatter,
        help='set values in assets'
    )
    cmd_set.set_defaults(run=commands.set)
    cmd_set.add_argument(
        '-d', '--depth',
        metavar='N',
        type=int,
        required=False,
        default=-1,
        help='descend at most "N" levels of directories below the starting-point; used only with --recursive'
    )
    cmd_set.add_argument(
        '-n', "--dry-run",
        required=False,
        default=False,
        action='store_true',
        help='perform a non-interactive trial-run without making any changes'
    )
    cmd_set.add_argument(
        '-q', '--quiet',
        required=False,
        default=False,
        action='store_true',
        help='silence output (requires the --yes flag)'
    )
    cmd_set.add_argument(
        '-R', '--recursive',
        required=False,
        default=False,
        action='store_true',
        help='set values recursively for all assets in a directory'
    )
    cmd_set.add_argument(
        '-y', '--yes',
        required=False,
        default=False,
        action='store_true',
        help='respond "yes" to any prompts'
    )
    cmd_set.add_argument(
        'keys',
        action=StoreDictKeyPair,
        metavar="KEYS",
        help='key-value pairs to set in assets; multiple pairs can be separated by commas (e.g. key=value,key2=value2)'
    )
    cmd_set.add_argument(
        'path',
        metavar='PATH',
        default='.',
        nargs='*',
        type=path,
        help='assets or directories for which to set values'
    )
    #
    # subcommand shell-completion
    #
    cmd_shell_completion = subcmds.add_parser(
        'shell-completion',
        description=textwrap.dedent(commands.shell_completion.__doc__),
        formatter_class=SubcommandHelpFormatter,
        help='shell completion for Onyo, suitable for use with "source"'
    )
    cmd_shell_completion.set_defaults(run=commands.shell_completion,
                                      parser=parser)
    cmd_shell_completion.add_argument(
        '-s', '--shell',
        metavar='SHELL',
        required=False,
        default='zsh',
        choices=['zsh'],
        help='shell to generate tab completion for'
    )
    #
    # subcommand "tree"
    #
    cmd_tree = subcmds.add_parser(
        'tree',
        description=textwrap.dedent(commands.tree.__doc__),
        formatter_class=SubcommandHelpFormatter,
        help='print the contents of a directory in a tree-like format'
    )
    cmd_tree.set_defaults(run=commands.tree)
    cmd_tree.add_argument(
        'directory',
        metavar='DIR',
        nargs='*',
        type=directory,
        help='directories to print'
    )
    return parser


def get_subcmd_index(arglist, start=1):
    """
    Get the index of the subcommand from a provided list of arguments (usually sys.argv).

    Returns the index on success, and None in failure.
    """
    # TODO: alternatively, this could use TabCompletion._argparse_to_dict()
    # flags which accept an argument
    flagplus = ['-C', '--onyopath']

    try:
        # find the first non-flag argument
        nonflag = next((a for a in arglist[start:] if a[0] != '-'))
        index = arglist.index(nonflag, start)
    except (StopIteration, ValueError):
        return None

    # check if it's the subcommand, or just an argument to a flag
    if arglist[index - 1] in flagplus:
        index = get_subcmd_index(arglist, index + 1)

    return index


def main():
    # NOTE: this unfortunately-located-hack is to pass uninterpreted args to
    # "onyo config".
    # nargs=argparse.REMAINDER is supposed to do this, but did not work for our
    # needs, and as of Python 3.8 is soft-deprecated (due to being buggy).
    # For more information, see https://docs.python.org/3.10/library/argparse.html#arguments-containing
    passthrough_subcmds = ['config']
    subcmd_index = get_subcmd_index(sys.argv)
    if subcmd_index and sys.argv[subcmd_index] in passthrough_subcmds:
        # display the subcmd's --help, and don't pass it through
        if not any(x in sys.argv for x in ['-h', '--help']):
            sys.argv.insert(subcmd_index + 1, '--')

    # parse the arguments
    parser = setup_parser()
    args = parser.parse_args()

    # debugging
    if args.debug:
        log.setLevel(logging.DEBUG)

    # run the subcommand
    if subcmd_index:
        args.run(args, args.onyopath)
    else:
        parser.print_help()
        exit(1)


if __name__ == '__main__':
    main()
