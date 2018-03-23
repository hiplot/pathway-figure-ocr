#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import json
from pathlib import Path
import psycopg2
import re
import os
import sys
from itertools import zip_longest

from gcv import gcv
from match import match
from ocr_pmc import ocr_pmc
from summarize import summarize


def clear(args):
    conn = psycopg2.connect("dbname=pfocr")
    words_cur = conn.cursor()
    ocr_processors__figures__words_cur = conn.cursor()

    try:
        ocr_processors__figures__words_cur.execute("DELETE FROM ocr_processors__figures__words;")
        words_cur.execute("DELETE FROM words;")
        conn.commit()

        os.remove("successes.txt")
        os.remove("fails.txt")
        os.remove("results.tsv")

        print('clear: SUCCESS')

    except(OSError, FileNotFoundError) as e:
        # we don't care if the file we tried to remove didn't exist 
        pass

    except(psycopg2.DatabaseError) as e:
        print('clear: FAIL')
        print('Error %s' % e)
        sys.exit(1)
        
    finally:
        if words_cur:
            words_cur.close()
        if ocr_processors__figures__words_cur:
            ocr_processors__figures__words_cur.close()
        if conn:
            conn.close()

def gcv_figures(args):
    def prepare_image(filepath):
        return filepath

    def do_gcv(prepared_filepath):
        gcv_result_raw = gcv(filepath=prepared_filepath, type='TEXT_DETECTION')
        if len(gcv_result_raw['responses']) != 1:
            print(gcv_result_raw)
            raise ValueError("""
                gcv_pmc.py expects the JSON result from GCV will always be {"responses": [...]},
                with "responses" having just a single value, but
                the result above indicates that assumption was incorrect.
                """)
        return gcv_result_raw['responses'][0]
    start = args.start
    end = args.end
    ocr_pmc(prepare_image, do_gcv, "gcv", start, end)

def load_figures(args):
    # TODO don't hard code things like the figure path
    pmcid_re = re.compile('^(PMC\d+)__(.+)')

    conn = psycopg2.connect("dbname=pfocr")
    papers_cur = conn.cursor()
    figures_cur = conn.cursor()

    p = Path(Path(__file__).parent)
    figure_paths = list(p.glob('../pmc/20150501/images_pruned/*.jpg'))

    pmcid_to_paper_id = dict();

    try:
        for figure_path in figure_paths:
            filepath = str(figure_path.resolve())
            name_components = pmcid_re.match(figure_path.stem)
            if name_components:
                pmcid = name_components[1]
                figure_number = name_components[2]
                print("Processing pmcid: " + pmcid + ", figure_number: " + figure_number)
                paper_id = None
                if pmcid in pmcid_to_paper_id:
                    paper_id = pmcid_to_paper_id[pmcid]
                else:
                    papers_cur.execute("INSERT INTO papers (pmcid) VALUES (%s) RETURNING id;", (pmcid, ))
                    paper_id = papers_cur.fetchone()[0]
                    pmcid_to_paper_id[pmcid] = paper_id

                figures_cur.execute("INSERT INTO figures (filepath, figure_number, paper_id) VALUES (%s, %s, %s);", (filepath, figure_number, paper_id))

        conn.commit()

        print('load_figures: SUCCESS')

    except(psycopg2.DatabaseError) as e:
        print('load_figures: FAIL')
        print('Error %s' % e)
        sys.exit(1)
        
    finally:
        if papers_cur:
            papers_cur.close()
        if figures_cur:
            figures_cur.close()
        if conn:
            conn.close()

# Create parser and subparsers
parser = argparse.ArgumentParser(
                prog='pfocr',
		description='''Process figures to extract pathway data.''')
subparsers = parser.add_subparsers(title='subcommands',
        description='valid subcommands',
        help='additional help')

# create the parser for the "clear" command
parser_clear = subparsers.add_parser('clear')
parser_clear.set_defaults(func=clear)

# create the parser for the "gcv_figures" command
parser_gcv_figures = subparsers.add_parser('gcv_figures',
        help='Run GCV on PMC figures and save results to database.')
parser_gcv_figures.add_argument('--start',
		type=int,
		help='start of figures to process')
parser_gcv_figures.add_argument('--end',
		type=int,
		help='end of figures to process')
parser_gcv_figures.set_defaults(func=gcv_figures)

# create the parser for the "load_figures" command
parser_load_figures = subparsers.add_parser('load_figures')
parser_load_figures.set_defaults(func=load_figures)

# create the parser for the "match" command
parser_match = subparsers.add_parser('match',
        help='Extract data from OCR result and put into DB tables.')
parser_match.add_argument('-n','--normalize',
		action='append',
		help='transform OCR result and lexicon')
parser_match.add_argument('-m','--mutate',
		action='append',
		help='transform only OCR result')

# create the parser for the "summarize" command
parser_summarize = subparsers.add_parser('summarize')
parser_summarize.set_defaults(func=summarize)

parser_match.set_defaults(func=match)

args = parser.parse_args()

# from python docs
def grouper(iterable, n, fillvalue=None):
    "Collect data into fixed-length chunks or blocks"
    # grouper('ABCDEFG', 3, 'x') --> ABC DEF Gxx"
    args = [iter(iterable)] * n
    return zip_longest(*args, fillvalue=fillvalue)

raw = sys.argv
normalization_flags = ["-n", "--normalize"]
mutation_flags = ["-m", "--mutate"]
if raw[1] == "match":
    transforms = []
    for arg_pair in grouper(raw[2:], 2, 'x'):
        category_raw = arg_pair[0]
        category_parsed = ""
        if category_raw in normalization_flags:
            category_parsed = "normalize"
        elif category_raw in mutation_flags:
            category_parsed = "mutate"

        if category_parsed:
            transforms.append({"name": arg_pair[1], "category": category_parsed})

    args.func(transforms)
else:
    args.func(args)