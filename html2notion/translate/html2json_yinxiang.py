from bs4 import BeautifulSoup, NavigableString, Tag
from ..utils import logger
from ..translate.html2json_base import Html2JsonBase, Block
from ..utils.timeutil import DateStrToISO8601

YinXiang_Type = "yinxiang"


class Html2JsonYinXiang(Html2JsonBase):
    input_type = YinXiang_Type

    def __init__(self, html_content):
        super().__init__(html_content)

    def process(self):
        soup = BeautifulSoup(self.html_content, 'html.parser')
        self.convert_children(soup)
        self.convert_properties(soup)
        return YinXiang_Type

    def convert_properties(self, soup):
        properties = {"title": "Unknown"}
        title_tag = soup.select_one('head > title')
        if title_tag:
            properties["title"] = title_tag.text

        meta_tags = [
            ('head > meta[name="source-url"]', "url"),
            ('head > meta[name="keywords"]', "tags", lambda x: x.split(",")),
            ('head > meta[name="created"]', "created_time", DateStrToISO8601),
        ]

        for selector, key, *converter in meta_tags:
            tag = soup.select_one(selector)
            if tag and tag.get('content', None):
                content = tag['content']
                properties[key] = converter[0](content) if converter else content

        self.properties = self.generate_properties(**properties)
        return

    def convert_children(self, soup):
        content_tags = soup.find_all('body', recursive=True)
        if not content_tags:
            logger.warning("No content found")
            return

        for child in content_tags[0].children:
            block_type = self.get_block_type(child)
            logger.debug(f'Support tag {child} with style {block_type}')
            converter = getattr(self, f"convert_{block_type}")
            if converter:
                block = converter(child)
                if block:
                    self.children.extend([block] if not isinstance(block, list) else block)
            else:
                logger.warning(f"Unknown block type: {block_type}")
    
    def convert_code(self, soup):
        json_obj = {
            "object": "block",
            "type": "code",
            "code": {
                "rich_text": [],
                "language": "plain text",
            },
        }
        rich_text = json_obj["code"]["rich_text"]

        children_list = list(soup.children) if isinstance(soup, Tag) else [soup]
        for index, child in enumerate(children_list):
            is_last_child = index == len(children_list) - 1
            text_obj = self.generate_inline_obj(child)
            if text_obj:
                rich_text.extend(text_obj)
            if not is_last_child:
                rich_text.append(self.generate_text(plain_text='\n'))
        json_obj["code"]["rich_text"] = self.merge_rich_text(rich_text)

        style = soup.get('style', "") if soup.name else ""
        css_dict = {}
        if isinstance(style, str):
            style = ''.join(style.split())
            css_dict = {rule.split(':')[0].strip(): rule.split(':')[1].strip() for rule in style.split(';') if rule}
            language = css_dict.get('--en-codeblockLanguage', 'plain text')
            json_obj["code"]["language"] = language
        
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

        children_list = list(soup.children)
        for index, child in enumerate(children_list):
            is_last_child = index == len(children_list) - 1
            text_obj = self.generate_inline_obj(child)
            if text_obj:
                rich_text.extend(text_obj)
            if not is_last_child:
                rich_text.append(self.generate_text(plain_text='\n'))

        # Merge tags has same anotions
        logger.debug(f'before merge: {rich_text}')
        json_obj["quote"]["rich_text"] = self.merge_rich_text(rich_text)
        return json_obj

    """
    <div>
    <div><br /></div>
    <table> <tbody> <tr> <td> </td> </tr> </tbody>
    <div><br /></div>
    </div>
    """
    # ../examples/insert_table.ipynb
    def convert_table(self, soup):
        # logger.debug(f'Convert table: {soup}')
        # Assert: only one table in table div
        table_rows = []
        tr_tags = soup.find_all('tr')
        if not tr_tags:
            logger.error(f"No tr found in {soup}")
            return
        
        table_width = len(tr_tags[0].find_all('td'))
        if table_width == 0:
            logger.error(f"No td found in {soup}")
            return
        
        for tr in tr_tags:
            td_tags = tr.find_all('td')
            one_row = {
                "type": "table_row",
                "table_row": {
                    "cells": []
                }
            }
            for td in td_tags:
                col = Html2JsonBase.generate_inline_obj(td)
                one_row["table_row"]["cells"].append(col)
            table_rows.append(one_row)

        table_obj = {
            "table": {
                "has_row_header": False,
                "has_column_header": False,
                "table_width": table_width,
                "children": table_rows,
            }
        }
        return table_obj

    def convert_to_do(self, soup: Tag):
        # Compatible with the situation where input is under li tag(super note).
        li_tags = soup.find_all('li', recursive=True)
        childs = li_tags if li_tags else [soup]
        to_do_blocks = []
        for child in childs:
            json_obj = {
                "object": "block",
                "type": "to_do",
                "to_do": {
                    "rich_text": [],
                    "checked": False
                }
            }
            text = json_obj["to_do"]["rich_text"]
            text_obj = self.generate_inline_obj(child)
            if text_obj:
                text.extend(text_obj)
            input_tag = child.find('input')
            if input_tag and isinstance(input_tag, Tag) and input_tag.get('checked', 'false') == 'true':
                json_obj["to_do"]["checked"] = True
            to_do_blocks.append(json_obj)
        return to_do_blocks
  
    def get_block_type(self, single_tag):
        tag_name = single_tag.name
        style = single_tag.get('style') if tag_name else ""

        # There are priorities here. It is possible to hit multiple targets 
        # at the same time, and the first one takes precedence.
        if self._check_is_todo(single_tag):
            return Block.TO_DO.value
        elif tag_name == 'hr':
            return Block.DIVIDER.value
        elif tag_name == 'ol':
            return Block.NUMBERED_LIST.value
        elif tag_name == 'ul':
            return Block.BULLETED_LIST.value
        elif tag_name == 'p':
            return Block.PARAGRAPH.value
        elif tag_name in ('h1', 'h2', 'h3', 'h4', 'h5', 'h6'):
            return Block.HEADING.value
        elif tag_name == 'table' or self._check_is_table(single_tag):
            return Block.TABLE.value
        if not style and tag_name == 'div':
            return Block.PARAGRAPH.value

        css_dict = {}
        if style:
            # Remove all space such as \t \n in style
            style = ''.join(style.split())
            css_dict = {rule.split(':')[0].strip(): rule.split(
                ':')[1].strip().lower() for rule in style.split(';') if rule}
        if css_dict.get('--en-blockquote', None) == 'true':
            return Block.QUOTE.value
        if css_dict.get('--en-codeblock', None) == 'true':
            return Block.CODE.value
        if css_dict.get('-en-codeblock', None) == 'true':
            return Block.CODE.value
        
        return Block.FAIL.value

    def _check_is_table(self, tag):
        if tag.name == "div":
            children = list(filter(lambda x: x != '\n', tag.contents))
            table_count = sum(1 for child in children if child.name == "table")
            div_br_count = sum(1 for child in children if child.name == "div" and len(
                child.contents) == 1 and child.contents[0].name == "br")

            return table_count == 1 and div_br_count >= 2 and (table_count + div_br_count) == len(children)
        return False

    def _check_is_todo(self, tag):
        if not isinstance(tag, Tag):
            return False
        input_tag = tag.find('input')
        if input_tag and isinstance(input_tag, Tag) and input_tag.get('type') == 'checkbox':
            return True
        return False

Html2JsonBase.register(YinXiang_Type, Html2JsonYinXiang)
