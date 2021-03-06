# Copyright 2020 Michael Daniels
# 
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
# 
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
# 
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

import pywikibot
import re
import MigrationRegexes
import time
from datetime import datetime, timezone
import wikitextparser as wtp
import sys

site = pywikibot.Site('commons', 'commons');
categoryName = "Category:License migration candidates";
# categoryName = "Category:License migration needs review";
optOutAutoPage = pywikibot.Page(site, "User:MDanielsBot/LROptOut#List (Automatic)");
optOutManualPage = pywikibot.Page(site, "User:MDanielsBot/LROptOut#List (Manual)");
mustBeBefore = datetime.utcfromtimestamp(1248998400);

# Computes if the file's EXIF data is too new
# Input: the file_info object given by pywikibot
# Returns: the bool photoTooNew, which is true if the photo is too new
#            and false if it is not.
def exif_too_new(file_info):
    try:
        file_metadata = file_info["metadata"];
    except:
        return False;
    
    if file_metadata is None: return False;
    
    # else
    datetime_str = next(filter(lambda x: x['name'] == 'DateTime', file_metadata),\
        {'value' : "0000:00:00 00:00:00"})['value'];
    try:
        theDatetime = datetime.strptime(datetime_str, "%Y:%m:%d %H:%M:%S");
    except Exception as e:
        return False

    original_datetime_str = next(filter(lambda x: x['name'] == 'DateTime',\
        file_metadata), {'value' : "0000:00:00 00:00:00"})['value'];
    if original_datetime_str == "0000:00:00 00:00:00":
        return False;
    original_datetime = datetime.strptime(original_datetime_str,\
                        "%Y:%m:%d %H:%M:%S");    
    
    photoTooNew = (original_datetime > mustBeBefore\
                  and theDatetime > mustBeBefore);
    
    return photoTooNew;

# Determines if there is an original upload date template. 
#    If there is none, return the string "nonefound"
#    If there is one, and it is too new for relicense, return "ineligible"
#    If there is one, and it shows that the photo is eligible, return eligible".
def process_orig_upload_date(revision):
    text = revision.text;
    
    if not text: return "nonefound";
    
    match = MigrationRegexes.origUploadDate_re1.search(text);
    
    if not match: return "nonefound";
    # else
    origUploadDate_str = ''.join(map(str, match.groups()))
    origUploadDate = datetime.strptime(origUploadDate_str, "%Y%m%d")
    
    print(origUploadDate)
    if (origUploadDate > mustBeBefore):
        return "ineligible";
    elif (origUploadDate < mustBeBefore):
        return "eligible";
    else:
        return "nonefound";
        
# Determines if there is an "original upload log" table with the
#     original upload date
#    If there is no wikitable, return the string "nonefound"
#    If there is one, and it is too new for relicense, return "ineligible"
#    If there is one, and it shows that the photo is eligible, return eligible".
def process_orig_upload_log(page):
    
    text = page.text;
    p = wtp.parse(text);
    if len(p.tables) == 0: return "nonefound";
    t = p.tables[0];

    col = t.data(column=0);
    if (col[0] != r"{{int:filehist-datetime}}"):
        return "nonefound";
    
    numuploads = len(col) - 1
    if (numuploads > 1): return "nonefound"; # Process these manually for now
    try:
        oldUploadDate = datetime.strptime(col[1], "%Y-%m-%d %H:%M");
        if (oldUploadDate <= mustBeBefore):
            return "eligible";
        elif (oldUploadDate > mustBeBefore):
            return "ineligible";
        else:
            return "nonefound";
    except:
        return "nonefound";

# Determines if there was 1 file version AND the file was imported with fileimporter. 
#    If this is false, return the string "nonefound"
#    If this is true, and it is too new for relicense, return "ineligible"
#    If this is true, and it shows that the photo is eligible, return eligible".
def process_fileimporter(page):
    
    if (MigrationRegexes.fileimporter_re.search(page.text) == None):
        return "nonefound"
    
    history = page.get_file_history()
    if len(history) > 1:
        return "nonefound"
    
    ts =  list(history.keys())[0]
    
    if ts >= mustBeBefore:
        return "ineligible"
    else:
        return "eligible"

# Performs replacements for pages ineligible for license migration
# Input: pywikibot page object
# Returns: True if replacement made, false if not
def migration_ineligible(page):
    rawtext = newtext = page.text
    text_tuple = pywikibot.textlib.extract_sections(rawtext)
    text = text_tuple[0]
    for sectionname, sectiontext in text_tuple[1]:
        if "{{Original upload log}}" in sectionname:
            continue
        else:
            text += sectionname + '\n' + sectiontext
    text += text_tuple[2]
    
    for match in MigrationRegexes.GFDL_re.finditer(text):
        oldstring = match.group(0);
        newstring = MigrationRegexes.GFDL_re.sub(
                    '{{GFDL\g<1>\g<2>\g<3>|migration=not-eligible}}',
                    oldstring, re.IGNORECASE
                    );
        newtext = newtext.replace(oldstring, newstring, 1);
    
    for match in MigrationRegexes.Self_re.finditer(text):
        oldstring = match.group(0);
        newstring = MigrationRegexes.Self_re.sub(
                    '{{self|\g<1>GFDL|migration=not-eligible}}',
                     oldstring, re.IGNORECASE
                     );
        newtext = newtext.replace(oldstring, newstring, 1);

    for match in MigrationRegexes.kettos_re.finditer(text):
        oldstring = match.group(0);
        newstring = MigrationRegexes.kettos_re.sub(
                    u'{{kettős-GFDL-cc-by-sa-2.5\g<1>|migration=not-eligible}}',
                     oldstring, re.IGNORECASE | re.UNICODE
                     );
        newtext = newtext.replace(oldstring, newstring, 1);
    
    if (newtext != rawtext):
        page.put(newtext, r'[[Commons:License_Migration_Task_Force/Migration'
                         + r'|License Migration]]: not-eligible')
        return True;
    # else
    return False;

# Performs replacements for pages ineligible for license migration
# Input: pywikibot page object
# Returns: True if replacement made, false if not
def migration_relicense(page):
    rawtext = newtext = page.text
    text_tuple = pywikibot.textlib.extract_sections(rawtext)
    text = text_tuple[0]
    for sectionname, sectiontext in text_tuple[1]:
        if "{{Original upload log}}" in sectionname:
            continue
        else:
            text += sectionname + '\n' + sectiontext
    text += text_tuple[2]
    
    for match in MigrationRegexes.GFDL_re.finditer(text):
        oldstring = match.group(0);
        newstring = MigrationRegexes.GFDL_re.sub(
                    u'{{GFDL\g<1>\g<2>\g<3>|migration=relicense}}',
                    oldstring, re.IGNORECASE | re.UNICODE
                    );
        newtext = newtext.replace(oldstring, newstring, 1);
    
    for match in MigrationRegexes.Self_re.finditer(text):
        oldstring = match.group(0);
        newstring = MigrationRegexes.Self_re.sub(
                    u'{{self|\g<1>GFDL|migration=relicense}}',
                     oldstring, re.IGNORECASE | re.UNICODE
                     );
        newtext = newtext.replace(oldstring, newstring, 1);

    for match in MigrationRegexes.kettos_re.finditer(text):
        oldstring = match.group(0);
        newstring = MigrationRegexes.kettos_re.sub(
                     u'{{kettős-GFDL-cc-by-sa-2.5\g<1>|migration=relicense}}',
                     oldstring, re.IGNORECASE | re.UNICODE
                     );
        newtext = newtext.replace(oldstring, newstring, 1);
    
    if (newtext != rawtext):
        page.put(newtext, r'[[Commons:License_Migration_Task_Force/Migration'
                         + r'|License Migration]]: relicensed')
        return True;
    # else
    return False;

# Computes whether migration would be redundant.
# If so, returns false.
# If not, performs replacements and returns true.
# Input: pywikibot page object
def migration_redundant(page):
    rawtext = newtext = page.text
    text_tuple = pywikibot.textlib.extract_sections(rawtext)
    text = text_tuple[0]
    for sectionname, sectiontext in text_tuple[1]:
        if "{{Original upload log}}" in sectionname:
            continue
        else:
            text += sectionname + '\n' + sectiontext
    text += text_tuple[2]
    
    redundant_re0 = re.compile('Cc-by-3\.0|Cc-by-sa-3\.0', re.IGNORECASE)
    if (redundant_re0.match(text) == None): return False;
    # Otherwise, continue
    
    for match in MigrationRegexes.redundant_re1.finditer(text):
        oldstring = match.group(0);
        newstring = MigrationRegexes.redundant_re1.sub(
                    '{{self|GFDL|cc-by-sa-3.0|\g<1>migration=redundant}}',\
                    oldstring, re.IGNORECASE);
        newtext = newtext.replace(oldstring, newstring, 1);
    
    for match in MigrationRegexes.redundant_re2.finditer(text):
        oldstring = match.group(0);
        newstring = MigrationRegexes.redundant_re2.sub(
                    '{{self|GFDL|cc-by-3.0|\g<1>migration=redundant}}'\
                    , oldstring, re.IGNORECASE);
        newtext = newtext.replace(oldstring, newstring, 1);
    
    for match in MigrationRegexes.redundant_re3.finditer(text):
        oldstring = match.group(0);
        newstring = MigrationRegexes.redundant_re3.sub(
                    '{{self|GFDL|cc-by-sa-3.0,2.5,2.0,1.0'
                    '|\g<1>migration=redundant}}'\
                    , oldstring, re.IGNORECASE);
        newtext = newtext.replace(oldstring, newstring, 1);
    
    if (MigrationRegexes.redundant_re4a.search(text) != None):
        for match in MigrationRegexes.redundant_re4b.finditer(text):
            oldstring = match.group(0);
            newstring = MigrationRegexes.redundant_re4b.sub(
                        '{{GFDL\g<1>|migration=redundant}}',
                        oldstring, re.IGNORECASE);
            newtext = newtext.replace(oldstring, newstring, 1);
            
    for match in MigrationRegexes.redundant_re5.finditer(text):
        oldstring = match.group(0);
        newstring = MigrationRegexes.redundant_re5.sub(
                    '{{self|\g<1>cc-by-sa-\g<2>|GFDL|migration=redundant}}',
                    oldstring, re.IGNORECASE);
        newtext = newtext.replace(oldstring, newstring, 1);
    
    if (newtext != rawtext):
        page.put(newtext, r'[[Commons:License_Migration_Task_Force/Migration'
                          + r'|License Migration]]: redundant')
        return True;
    
    return False;

# Performs replacements for pages where the uploader opted out.
# Returns true if replacement made, false if not.
def migration_opt_out(page):
    rawtext = newtext = page.text
    text_tuple = pywikibot.textlib.extract_sections(rawtext)
    text = text_tuple[0]
    for sectionname, sectiontext in text_tuple[1]:
        if "{{Original upload log}}" in sectionname:
            continue
        else:
            text += sectionname + '\n' + sectiontext
    text += text_tuple[2]
    
    for match in MigrationRegexes.GFDL_re.finditer(text):
        oldstring = match.group(0);
        newstring = MigrationRegexes.GFDL_re.sub(
                    u'{{GFDL\g<1>\g<2>\g<3>|migration=opt-out}}',
                    oldstring, re.IGNORECASE | re.UNICODE
                    );
        newtext = newtext.replace(oldstring, newstring, 1);
    
    for match in MigrationRegexes.Self_re.finditer(text):
        oldstring = match.group(0);
        newstring = MigrationRegexes.GFDL_re.sub(
                    u'{{self|\g<1>GFDL|migration=opt-out}}',
                     oldstring, re.IGNORECASE | re.UNICODE
                     );
        newtext = newtext.replace(oldstring, newstring, 1);

    for match in MigrationRegexes.kettos_re.finditer(text):
        oldstring = match.group(0);
        newstring = MigrationRegexes.kettos_re.sub(
                     u'{{kettős-GFDL-cc-by-sa-2.5\g<1>|migration=opt-out}}',
                     oldstring, re.IGNORECASE | re.UNICODE
                     );
        newtext = newtext.replace(oldstring, newstring, 1);
    
    if (newtext != rawtext):
        page.put(newtext, r'[[Commons:License_Migration_Task_Force/Migration'
                         + r'|License Migration]]: User opted out')
        return True;
    else:
        return False;

# Determines if the page is ineligible for migration
# Input: Page object. Output: bool.
def isineligible(page):
    oldestFInfo = page.oldest_file_info;
    latestFInfo = page.latest_file_info;
    return ( (exif_too_new(latestFInfo) and exif_too_new(oldestFInfo)) or \
            (process_orig_upload_date(page.latest_revision) == "ineligible") or \
            (process_orig_upload_log(page) == "ineligible") or \
            (process_fileimporter(page) == "ineligible") );

# Simple helper function to determine if eligible for migration.
# Input: Page object. Output: bool.
def isEligible(page):
    return (process_orig_upload_date(page.latest_revision) == "eligible") or\
          (process_orig_upload_log(page) == "eligible") or \
          (process_fileimporter(page) == "eligible")

# Return 1 if user is opted out manually, 2 if automatically, 0 if neither.
def isOptedOut(page):
    for link in page.linkedPages(namespaces=2):
        for user in optOutManualPage.linkedPages(namespaces=2):
            if (link == user): return 1;
        for user in optOutAutoPage.linkedPages(namespaces=2):
            if (link == user): return 2;
    
    # If nothing
    return 0;

def main():
    cat = pywikibot.Category(site, categoryName)
    i = 0;
    # for page in cat.articles(startprefix="F"):
    for page in cat.articles():
    # page = pywikibot.FilePage(site, "File:BariIcircoscrizione.gif")
    # while i == 0:
        i = i + 1;
        sys.stdout.flush()
        # time.sleep(0.3)
        
        # If the file is redundant, it doesn't matter if it's ineligible.
        if migration_redundant(page):
            # Function already did replacement
            print('Migration redundant, i = {0}.'.format(i))
        elif isineligible(page):
            # If the changes succeeded
            if (migration_ineligible(page)):
                print('Migration ineligible, i = {0}.'.format(i));
            # If it failed
            else:
                print("BEGIN PAGE {0} ({1}):".format(i, page.title()))
                print(page.get())
                print("END PAGE {0}".format(i))
                print(('Migration ineligible, but no replacement made!'\
                 + ' (i= {0})').format(i));
        elif (isOptedOut(page) == 1):
            # User in the Opted out -- manual list
            
            # Was going to perform replacement, but skip for now.
            # migration_opt_out(page);
            continue;
        elif (isOptedOut(page) == 2):
            # User in the Opted out -- automatic list
            # Skip (at least for now)
            continue;
        elif isEligible(page):
                if migration_relicense(page):
                    print('Migration relicensed, i = {0}.'.format(i));
                    continue;
                else:
                    print("BEGIN PAGE {0} ({1}):".format(i, page.title()))
                    print(page.get())
                    print("END PAGE {0}".format(i))
                    print(('Migration eligible, but no replacement made!'\
                     + ' (i= {0})').format(i))
        else:
            print("BEGIN PAGE {0} ({1}):".format(i, page.title()))
            print(page.get())
            print("END PAGE {0}".format(i))
            print(('Nothing to do here? (i= {0})').format(i));
    # End loop

if __name__ == "__main__":
    main();