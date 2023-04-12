import cssutils
from bs4 import BeautifulSoup
from ..utils import logger
from ..translate.html2json_base import Html2JsonBase


YinXiang_Type = "yinxiang"


class Html2JsonYinXiang(Html2JsonBase):
    input_type = YinXiang_Type

    inline_tags = {"a", "abbr", "acronym", "b", "cite", "code", "em", "i",
                   "img", "kbd", "q", "samp", "small", "span", "strong",
                   "sub", "sup", "u"}

    def __init__(self, html_content):
        super().__init__(html_content)

    def process(self):
        self.convert()
        return YinXiang_Type

    def convert(self):
        soup = BeautifulSoup(self.html_content, 'html.parser')
        div_tags = soup.find_all('div', recursive=True)

        for child in div_tags:
            is_dup = False
            for parent in child.find_parents():
                if parent.name == 'div':
                    logger.debug("Filter child div")
                    is_dup = True
                    break
            if is_dup:
                continue
            
            div_type = self.get_div_type(child)

            if div_type == "paragraph":
                parapraph = self.convert_paragraph(child)
                if parapraph:
                    self.children.append(parapraph)
            elif div_type == "quote":
                quote = self.convert_quote(child)
                if quote:
                    self.children.append(quote)

    def convert_paragraph(self, soup):
        json_obj = {
            "object": "block",
            "type": "paragraph",
            "paragraph": {
                "rich_text": []
            }
        }
        rich_text = json_obj["paragraph"]["rich_text"]
        for child in soup.children:
            tag_name = child.name.lower() if child.name else ""
            tag_text = child.text if child.text else ""
            if not tag_text:
                continue
            style = child.get('style') if child.name else ""
            tag_style = cssutils.parseStyle(style)
            text_obj = self.parse_inline_tag(tag_name, tag_text, tag_style)
            if text_obj:
                rich_text.append(text_obj)

        return json_obj

    def convert_quote(self, soup):
        json_obj = {
            "object": "block",
            "type": "quote",
            "quote": {
                "rich_text": []
            }
        }
        rich_text = json_obj["quote"]["rich_text"]
        for child in soup.children:
            tag_name = child.name.lower() if child.name else ""
            tag_text = child.text if child.text else ""
            if not tag_text:
                continue
            style = child.get('style') if child.name else ""
            tag_style = cssutils.parseStyle(style)
            text_obj = self.parse_inline_tag(tag_name, tag_text, tag_style)
            if text_obj:
                rich_text.append(text_obj)

        return json_obj
    
    # Todo
    # <b><u>下划线粗体</u></b>
    def parse_inline_tag(self, tag_name, tag_text, styles):
        if tag_name not in Html2JsonYinXiang.inline_tags:
            logger.warn(f"Not support tag {tag_name}")
        text_params = {}
        text_params["plain_text"] = tag_text
        if Html2JsonBase.is_bold(tag_name, styles):
            text_params["bold"] = True
        if Html2JsonBase.is_italic(tag_name, styles):
            text_params["italic"] = True
        if Html2JsonBase.is_strikethrough(tag_name, styles):
            text_params["strikethrough"] = True
        if Html2JsonBase.is_underline(tag_name, styles):
            text_params["underline"] = True

        color = Html2JsonBase.get_color(styles)
        if color != 'default':
            text_params["color"] = color
        text_obj = self.generate_text(**text_params)
        return text_obj

    def get_div_type(self, div_tag):
        style = div_tag.get('style') if div_tag.name else ""
        if not style:
            return Html2JsonBase.notion_block_types["paragraph"]
        # styles = cssutils.parseStyle(style)
        # block = styles.getPropertyValue('-en-codeblock', False)
        css_dict = {rule.split(':')[0].strip(): rule.split(
            ':')[1].strip() for rule in style.split(';') if rule}
        en_codeblock = css_dict.get('-en-codeblock', None)
        if en_codeblock == 'true':
            return Html2JsonBase.notion_block_types["quote"]

Html2JsonBase.register(YinXiang_Type, Html2JsonYinXiang)
