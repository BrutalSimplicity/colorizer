from pygments import highlight
from pygments.lexers import get_lexer_by_name, guess_lexer, get_all_lexers
from pygments.formatters import HtmlFormatter
from pygments.styles import get_all_styles
from lxml import etree
from lxml.etree import HTMLParser, ParseError
import sys
import argparse
from os import linesep

def colorize_node(node, formatter, lexer):
    html_hilite = highlight(node.text, lexer, formatter)

    if html_hilite:
        # when building the html tree in lxml it automatically embeds the html
        # in html/body tags so we need to travel back to the stuff we want
        code_tree = etree.fromstring(html_hilite, HTMLParser())
        div_tree = code_tree.xpath('/html/body/node()[1]')[0]
        # we need to find what tags to replace
        # if this is a <code> tag by itself, just replace the text
        # if it is a <code> tag that is the child of a <pre> tag, replace the pre node
        # if it is a <pre> tag by itself, just replace 
        if node.tag == 'code':
            if node.getparent().tag == 'pre':  # <pre><code> tags
                parent = node.getparent().getparent()
                parent.replace(node.getparent(), div_tree)
            else:  # <code> tag only
                parent = node.getparent()
                parent.replace(node, div_tree)
        else:  # <pre> tag only
            parent = node.getparent()
            parent.replace(node, div_tree)


def colorize(plain_html, default='', style='default', border='', inline=False, linenos=False):
    tree = etree.fromstring(plain_html, HTMLParser())
    formatter = HtmlFormatter(style=style, linenos=linenos, cssstyles=border, 
                              noclasses=inline, cssclass='colorize')

    # iterate over all code tags and pre tags who do not have
    # a nested code tag
    converted = 0
    log = []
    for code_elem in tree.xpath('//code | //pre[not(code)]'):
        found_lexer = False
        if not code_elem.text:
            continue

        if code_elem.attrib.has_key('class') and code_elem.attrib['class']:
            try:
                log.append('Using lexer [%s] on tag <%s> @ line %d' % (code_elem.attrib['class'], code_elem.tag, code_elem.sourceline))
                # throws an exception if lexer is not found
                lexer = get_lexer_by_name(code_elem.attrib['class'])
                colorize_node(code_elem, formatter, lexer)
                found_lexer = True
                converted += 1
            except Exception as e:
                log.append('Error on tag <%s> @ line %d :: %s' % (code_elem.tag, code_elem.sourceline, e))

        # if finding the lexer by tag and class name fails, we'll fall to the default
        # only if the code contains multiple lines (this tries to avoid inlined code)
        if not found_lexer and default and len(str.splitlines(code_elem.text)) > 1:
            try:
                log.append('Using default lexer [%s] on tag <%s> @ line %d' % (default, code_elem.tag, code_elem.sourceline))
                lexer = get_lexer_by_name(default)
                colorize_node(code_elem, formatter, lexer)
                found_lexer = True
                converted += 1
            except Exception as e:
                log.append('Error on tag <%s> @ line %d :: %s' % (code_elem.tag, code_elem.sourceline, e))
                continue

        # lastly, if there is no default defined, we'll try to guess the lexer.
        # this seems to be hit or miss
        if not found_lexer and not default and len(str.splitlines(code_elem.text)) > 1:
            try:
                log.append('No default lexer, attempting to guess <%s> @ line %d' (code_elem.tag, code_elem.sourceline))
                # throws an exception on failure
                lexer = guess_lexer(code_elem.text)
                log.append('Lexer guess succeeded, using [%s] on tag <%s> @ line %d' (lexer.alias[0], code_elem.tag, code_elem.sourceline))
                colorize_node(code_elem, formatter, lexer)
                converted += 1
            except Exception as e:
                log.append('Error on tag <%s> @ line %d :: %s' % (code_elem.tag, code_elem.sourceline, e))
                continue

    script = ''
    if converted > 0:
        script = formatter.get_style_defs('.colorize')

        if not inline:
            style_tag = tree.xpath('/html/head/style')
            if style_tag:
                style_tag[0].text += script
            else:
                head_tag = tree.xpath('/html/head')
                head_tag = head_tag[0] if head_tag else None
                if not head_tag:
                    tree.insert(0, etree.Element('head'))
                    head_tag = tree.find('head')
                style = etree.Element('style')
                style.text = script
                head_tag.append(style)

        html_result = etree.tostring(tree, method='html', pretty_print=True)
    else:
        html_result = html_hilite

    return (converted > 0), log, converted, html_result, script


if __name__ == '__main__':
    parser = argparse.ArgumentParser(prog='colorize',
                                     description='Add syntax highlighting to code in html. Built using Pygments. http://pygments.org/',
                                     usage='%(prog)s [options]')
    parser.add_argument('-f', '--htmlfile', help='The html file to process')
    parser.add_argument('-s', '--style', help='The style of syntax highlighting. See --list_styles for a full list')
    parser.add_argument('--list_styles', action='store_true', help='List of possible syntax styles to use')
    parser.add_argument('-d', '--default', help='Default lexer to use (i.e. csharp, python). See --list_lexers or --find_lexer for a full list')
    parser.add_argument('--list_lexers', action='store_true', help='List of lexers to choose from')
    parser.add_argument('--find_lexer', help='Find a lexer')
    parser.add_argument('--div_style',
                        help='The inline css style to apply to the <div> tag surrounding each code block (Ignored if --div_file is used)')
    parser.add_argument('--div_file',
                        help='The file to use as the inline css style to apply to the <div> tag surrounding each code block')
    parser.add_argument('-l', '--linenos', action='store_true', help='Add line numbers to the code blocks')
    parser.add_argument('-i', '--inline', action='store_true',
                        help='Create css styles inline on each tag as opposed to a separate styles section')
    parser.add_argument('-o', '--out', help='Write results to this file')
    parser.add_argument('--css_file',
                        help='Write code styles to this file. This still writes new styles into the style tag (Ignored if --inline is used)')
    parser.add_argument('--log', action='store_true', help='Log errors to "log.txt" in the same directory')
    args = parser.parse_args()

    if args.list_styles:
        for style in get_all_styles():
            print style
        exit()
    if args.list_lexers:
        for lexer in get_all_lexers():
            print lexer[0] + ' :: [' + str.join(', ', [alias for alias in lexer[1]]) + ']'
        exit()
    if args.find_lexer:
        for lexer in get_all_lexers():
            if args.find_lexer in lexer[1]:
                print lexer[0] + ' :: [' + str.join(', ', [alias for alias in lexer[1]]) + ']'
                exit()
        print 'Lexer not found.'
        exit()

    if not args.htmlfile:
        print 'usage: colorize [options]'
        print 'colorize: error: use -f htmlfile to begin or -h for help'
        exit()

    if args.style and not args.style in get_all_styles():
        print 'Style not found. Use --list_styles to see a list of available styles.'
        exit()

    if args.default and not args.default in [a for l in get_all_lexers() for a in l[1]]:
        print 'Default lexer not found. Use --list_lexers to see a list of available lexers.'
        exit()

    success = False
    log = None
    converted = 0
    html_hilite = ''
    script = ''
    try:
        with open(args.htmlfile) as f:
            html = f.read()
            inline_div = args.div_style if args.div_style else ''
            if args.div_file:
                with open(args.div_file) as fb:
                    inline_div = fb.read()

            style = args.style if args.style else 'default'
            default = args.default if args.default else ''
            success, log, converted, html_hilite, script = colorize(html, default, style, inline_div, args.inline, args.linenos)

            if success:
                if args.out:
                    with open(args.out, 'w') as f:
                        f.write(html_hilite)
                else:
                    print html_hilite

                if args.css_file:
                    with open(args.css_file, 'w') as fcss:
                        fcss.write(script)

                if args.log:
                    with open('log.txt', 'w') as flog:
                        flog.write(str.join(linesep, log))

                print '%d code blocks colorized!' % (converted)
                if not args.default:
                    print 'If the html output is not as expected try adding the --default option to specify a default lexer'
            else:

                if args.log:
                    with open('log.txt', 'w') as flog:
                        flog.write(str.join(linesep, log))

                print 'Colorize did not convert any code blocks. Use the --log switch to enable error logging.'
                if not args.default:
                    print 'You also might try using the --default option to specify a default lexer'

    except IOError as e:
        print 'An I/O error occurred: ' + e
    except ParseError as e:
        print 'An error occurred parsing the html document: ' + e