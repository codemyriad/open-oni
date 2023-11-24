import os
import fitz
import shutil
from xml.dom.minidom import parseString

from optparse import make_option

from django.core.management.base import BaseCommand
from django.core.management.base import CommandError

from pdf2image import convert_from_path
from xml.etree.ElementTree import Element, SubElement, ElementTree, tostring, QName


class Command(BaseCommand):
    """
    Create an Open ONI batch out of a PDF.

    Example invocation:

        python manage.py import_pdf_to_batch --batch-name=<batch_name> --institutional-code=<institutional_code> --version=<version> --lccn=<lccn> --issue-date=<issue_date> --output-path=<output_path> <pdf_path>
    """

    help = "Generate an Open ONI batch out of a PDF"

    def add_arguments(self, parser):
        parser.add_argument("pdf_path", nargs=1, type=str, help="Path to the PDF file")
        parser.add_argument(
            "--batch-name",
            dest="batch_name",
            default="",
            help="Name of the resulting batch",
        )
        parser.add_argument(
            "--institutional-code",
            dest="institutional_code",
            default="",
            help="Institutional code",
        )
        parser.add_argument(
            "--version", dest="version", default="01", help="Issue version"
        )
        parser.add_argument(
            "--lccn", dest="lccn", default="", help="Library of Congress Call Number"
        )
        parser.add_argument(
            "--issue-date",
            dest="issue_date",
            default="",
            help="Issue date in YYYYMMDD format",
        )
        parser.add_argument(
            "--output-path",
            dest="output_path",
            default="data/batches",
            help="Output path for the batch",
        )

    def handle(self, batch_path, *args, **options):
        # Check if required options are provided
        required_options = ["batch_name", "institutional_code", "issue_date"]
        for option in required_options:
            if not options[option]:
                raise CommandError(f"Error: Required option '{option}' is missing.")

        pdf_path = options["pdf_path"][0]
        batch_name = options["batch_name"]
        institutional_code = options["institutional_code"]
        version = options["version"]
        lccn = options["lccn"]
        issue_date = options["issue_date"]
        output_path = options["output_path"]
        reel_number = "01"  # We don't really need this for now

        self.stdout.write(f"PDF Path: {pdf_path}")
        self.stdout.write(f"Batch Name: {batch_name}")
        self.stdout.write(f"Institutional Code: {institutional_code}")
        self.stdout.write(f"Version: {version}")
        self.stdout.write(f"LCCN: {lccn}")
        self.stdout.write(f"Issue Date: {issue_date}")
        self.stdout.write(f"Output Path: {output_path}")

        # Check if the PDF file exists
        if not os.path.isfile(pdf_path):
            self.stderr.write(f"Error: PDF file not found at path: {pdf_path}\n")
            return

        self.create_open_oni_batch(
            pdf_file_path,
            output_path,
            batch_name,
            institutional_code,
            version,
            lccn,
            reel_number,
            issue_code,
        )

    def create_open_oni_batch(
        pdf_file_path,
        output_path,
        batch_name,
        institutional_code,
        version,
        lccn,
        reel_number,
        issue_code,
    ):
        # Create the Open-ONI batch directory structure
        batch_folder_name = f"batch_{institutional_code}_{batch_name}_ver{version}"
        issue_date = f"{issue_code[:4]}-{issue_code[4:6]}-{issue_code[6:8]}"
        issue_directory = self.create_open_oni_batch_folder_structure(
            output_path, batch_folder_name, lccn, reel_number, issue_code
        )

        pdf_file = fitz.open(pdf_file_path)

        # Create batch root element
        batch = Element(
            "batch",
            attrib={
                "xmlns": "http://www.loc.gov/ndnp",
                "name": batch_name,
                "awardee": institutional_code,
                "awardYear": issue_code[:4],
            },
        )

        # Create METS root element
        mets = Element(
            "mets",
            attrib={
                "TYPE": "urn:library-of-congress:ndnp:mets:newspaper:issue",
                "PROFILE": "urn:library-of-congress:mets:profiles:ndnp:issue:v1.5",
                "LABEL": f"{institutional_code} {issue_date}",
                "xmlns": "http://www.loc.gov/METS/",
                "xmlns:xlink": "http://www.w3.org/1999/xlink",
                "xmlns:mods": "http://www.loc.gov/mods/v3",
                "xmlns:mix": "http://www.loc.gov/mix/",
            },
        )

        # Add issue metadata
        dmd_id = "issueModsBib"
        dmd_sec = SubElement(mets, "dmdSec", ID=dmd_id)
        md_wrap = SubElement(dmd_sec, "mdWrap", LABEL="Issue metadata", MDTYPE="MODS")
        xml_data = SubElement(md_wrap, "xmlData")
        mods = SubElement(xml_data, "mods:mods")
        mods_related = SubElement(mods, "mods:relatedItem", type="host")
        mods_identifier = SubElement(mods_related, "mods:identifier", type="lccn")
        mods_identifier.text = lccn
        mods_part = SubElement(mods_related, "mods:part")
        mods_detail = SubElement(mods_part, "mods:detail", type="edition")
        mods_number = SubElement(mods_detail, "mods:number")
        mods_number.text = version
        mods_origin = SubElement(mods, "mods:originInfo")
        mods_date = SubElement(mods_origin, "mods:dateIssued", encoding="iso8601")
        mods_date.text = issue_date
        mods_note = SubElement(mods, "mods:note", type="noteAboutReproduction")
        mods_note.text = "Present"

        file_sec = SubElement(mets, "fileSec")
        struct_map = SubElement(
            mets,
            "structMap",
            attrib={"xmlns:np": "urn:library-of-congress:ndnp:mets:newspaper"},
        )
        issue_div = SubElement(struct_map, "div", TYPE="np:issue", DMDID=dmd_id)

        amd_sec = SubElement(mets, "amdSec")
        for admid in [
            "premisotherDerivativeFile",
            "mixserviceFile",
            "mixmasterFile",
            "premisocrFile",
        ]:
            tech_md = SubElement(amd_sec, "techMD", ID=admid)
            # Get page size of the first page from MediaBox
            md_wrap = SubElement(
                tech_md, "mdWrap", LABEL="PDF Image metadata", MDTYPE="PDFIMG"
            )
            xml_data = SubElement(md_wrap, "xmlData")
            mix_mix = SubElement(xml_data, "mix:mix")
            mix_imaging_performance = SubElement(
                mix_mix, "mix:ImagingPerformanceAssessment"
            )
            mix_spatial_metrics = SubElement(
                mix_imaging_performance, "mix:SpatialMetrics"
            )
            mix_image_width = SubElement(mix_spatial_metrics, "mix:ImageWidth")
            mix_image_width.text = str(int(pdf_file[0].mediabox[-2]))
            mix_image_length = SubElement(mix_spatial_metrics, "mix:ImageLength")
            mix_image_length.text = str(int(pdf_file[0].mediabox[-1]))

        # Extract images from the PDF
        images = convert_from_path(pdf_file_path)

        total_pages = len(pdf_file)
        for page_number in range(total_pages):

            print(f"Processing page {page_number + 1} of {total_pages}...")
            page = pdf_file[page_number]
            padded_page_number = self.format_number_with_padding(page.number + 1)

            # Add page metadata
            dmd_id = f"pageModsBib{page_number + 1}"
            dmd_sec = SubElement(mets, "dmdSec", ID=dmd_id)
            md_wrap = SubElement(
                dmd_sec, "mdWrap", LABEL="Page metadata", MDTYPE="MODS"
            )
            xml_data = SubElement(md_wrap, "xmlData")
            mods = SubElement(xml_data, "mods:mods")

            mods_part = SubElement(mods, "mods:part")
            mods_extent = SubElement(mods_part, "mods:extent", unit="pages")
            mods_start = SubElement(mods_extent, "mods:start")
            mods_start.text = str(page_number + 1)

            mods_related = SubElement(mods, "mods:relatedItem", type="original")
            mods_physical_description = SubElement(
                mods_related, "mods:physicalDescription"
            )
            mods_form = SubElement(
                mods_physical_description, "mods:form", type="microfilm"
            )

            mods_identifier = SubElement(
                mods_related, "mods:identifier", type="reel number"
            )
            mods_identifier.text = reel_number
            # mods_identifier = SubElement(mods_related, "mods:identifier", type="reel sequence number")
            # mods_identifier.text = ??

            mods_location = SubElement(mods_related, "mods:location")
            mods_physical_location = SubElement(
                mods_location,
                "mods:physicalLocation",
                authority="marcorg",
                displayLabel="La Masca; Cuneo, Italy",
            )
            mods_physical_location.text = institutional_code

            mods_note = SubElement(
                mods,
                "mods:note",
                displayLabel="La Masca; Cuneo, Italy",
                type="agencyResponsibleForReproduction",
            )
            mods_note.text = institutional_code

            mods_note = SubElement(mods, "mods:note", type="noteAboutReproduction")
            mods_note.text = "Present"

            page_div = SubElement(
                issue_div, "div", TYPE="np:page", DMDID=f"pageModsBib{page.number + 1}"
            )

            pdf_page_file_path = os.path.join(
                issue_directory, f"{padded_page_number}.pdf"
            )
            tif_image_file_path = os.path.join(
                issue_directory, f"{padded_page_number}.tif"
            )
            jp2_image_file_path = os.path.join(
                issue_directory, f"{padded_page_number}.jp2"
            )

            # Get page size from MediaBox
            media_box = page.mediabox
            page_width, page_height = media_box[-2], media_box[-1]

            # Save the page as a separate PDF
            if not os.path.exists(pdf_page_file_path):
                pdf_page = fitz.open()
                pdf_page.insert_pdf(
                    pdf_file, from_page=page.number, to_page=page.number
                )
                pdf_page.save(pdf_page_file_path)
                pdf_page.close()

            file_id = f"otherDerivativeFile{page.number + 1}"
            file_group = SubElement(file_sec, "fileGrp")
            file_tag = SubElement(
                file_group,
                "file",
                ADMID=f"premisotherDerivativeFile",
                ID=file_id,
                USE="derivative",
            )
            file_loc = SubElement(
                file_tag,
                "FLocat",
                LOCTYPE="OTHER",
                OTHERLOCTYPE="file",
                xlink="http://www.w3.org/1999/xlink",
            )
            file_loc.set("xlink:href", f"./{os.path.basename(pdf_page_file_path)}")

            file_struct = SubElement(page_div, "fptr", FILEID=file_id)

            if not os.path.exists(jp2_image_file_path):
                image = images[page.number]
                image.save(jp2_image_file_path, "JPEG2000")

            file_id = f"serviceFile{page.number + 1}"
            file_group = SubElement(file_sec, "fileGrp")
            file_tag = SubElement(
                file_group, "file", ADMID=f"mixserviceFile", ID=file_id, USE="service"
            )
            file_loc = SubElement(
                file_tag,
                "FLocat",
                LOCTYPE="OTHER",
                OTHERLOCTYPE="file",
                xlink="http://www.w3.org/1999/xlink",
            )
            file_loc.set("xlink:href", f"./{os.path.basename(jp2_image_file_path)}")

            file_struct = SubElement(page_div, "fptr", FILEID=file_id)

            if not os.path.exists(tif_image_file_path):
                image.save(tif_image_file_path, "TIFF")

            file_id = f"masterFile{page.number + 1}"
            file_group = SubElement(file_sec, "fileGrp")
            file_tag = SubElement(
                file_group, "file", ADMID=f"mixmasterFile", ID=file_id, USE="master"
            )
            file_loc = SubElement(
                file_tag,
                "FLocat",
                LOCTYPE="OTHER",
                OTHERLOCTYPE="file",
                xlink="http://www.w3.org/1999/xlink",
            )
            file_loc.set("xlink:href", f"./{os.path.basename(tif_image_file_path)}")

            file_struct = SubElement(page_div, "fptr", FILEID=file_id)

            # Create an ALTO XML structure
            alto_xml = self.generate_alto_xml(page, page_width, page_height)
            alto_file_path = os.path.join(issue_directory, f"{padded_page_number}.xml")

            # Save ALTO XML to a file
            with open(alto_file_path, "w", encoding="utf-8") as alto_xml_file:
                alto_xml_file.write(alto_xml)

            # Create METS file references
            file_id = f"ocrFile{page.number + 1}"
            file_group = SubElement(file_sec, "fileGrp")
            file_tag = SubElement(
                file_group, "file", ADMID=f"premisocrFile", ID=file_id, USE="ocr"
            )
            file_loc = SubElement(
                file_tag,
                "FLocat",
                LOCTYPE="OTHER",
                OTHERLOCTYPE="file",
                xlink="http://www.w3.org/1999/xlink",
            )
            file_loc.set("xlink:href", f"./{os.path.basename(alto_file_path)}")

            file_struct = SubElement(page_div, "fptr", FILEID=file_id)

        # Save the METS XML
        mets_file_path = os.path.join(issue_directory, f"{issue_code}.xml")
        mets_xml = parseString(tostring(mets, encoding="utf-8").decode()).toprettyxml()
        with open(mets_file_path, "w", encoding="utf-8") as mets_xml_file:
            mets_xml_file.write(mets_xml)

        issue_tag = SubElement(
            batch, "issue", editionOrder=version, issueDate=issue_date, lccn=lccn
        )
        mets_file_relative_path = mets_file_path.split(f"{batch_folder_name}/data")[1]
        issue_tag.text = f".{mets_file_relative_path}"

        # Save the batch XML
        batch_file_path = os.path.join(
            output_path, batch_folder_name, "data", f"batch.xml"
        )
        batch_validation_file_path = os.path.join(
            output_path, batch_folder_name, "data", f"batch_1.xml"
        )
        batch_xml = parseString(
            tostring(batch, encoding="utf-8").decode()
        ).toprettyxml()
        with open(batch_file_path, "w", encoding="utf-8") as batch_xml_file:
            batch_xml_file.write(batch_xml)
        with open(batch_validation_file_path, "w", encoding="utf-8") as batch_xml_file:
            batch_xml_file.write(batch_xml)

        print(f"Open-ONI batch folder created at: {issue_directory}")

    def format_number_with_padding(number):
        return f"{number:04d}"

    def create_open_oni_batch_folder_structure(
        root_folder, batch_folder_name, lccn, reel_number, issue_code
    ):
        # Create the root directory if it doesn't exist
        issue_folder_path = os.path.join(
            root_folder, batch_folder_name, "data", lccn, reel_number, issue_code
        )
        os.makedirs(issue_folder_path, exist_ok=True)
        return issue_folder_path

    def get_element_coordinates(raw_coordinates):
        return dict(
            HPOS=str(raw_coordinates[0]),
            VPOS=str(raw_coordinates[1]),
            WIDTH=str(raw_coordinates[2] - raw_coordinates[0]),
            HEIGHT=str(raw_coordinates[3] - raw_coordinates[1]),
        )

    def generate_alto_xml(pdf_page, page_width, page_height):
        # Create METS-ALTO XML for each page
        alto = Element("alto", xmlns="http://www.loc.gov/standards/alto/ns-v4#")
        layout = SubElement(alto, "Layout")

        page = SubElement(
            layout,
            "Page",
            ID=f"{self.format_number_with_padding(pdf_page.number + 1)}",
            WIDTH=str(page_width),
            HEIGHT=str(page_height),
        )
        page_space = SubElement(page, "PrintSpace")

        for block in pdf_page.get_text("rawdict").get("blocks", []):
            text_block = SubElement(
                page_space,
                "TextBlock",
                language="ita",
                **self.get_element_coordinates(block["bbox"]),
            )
            for line in block.get("lines", []):
                text_line = SubElement(
                    text_block, "TextLine", **self.get_element_coordinates(line["bbox"])
                )
                for span in line.get("spans"):
                    chars = span.get("chars")
                    word = []
                    for index, char in enumerate(chars):
                        if char["c"] == " ":
                            # We hit a whitespace
                            if word:
                                # Let's write the word down
                                text_word = SubElement(
                                    text_line,
                                    "String",
                                    CONTENT="".join([char["c"] for char in word]),
                                    **self.get_element_coordinates(
                                        fitz.recover_span_quad(
                                            line["dir"], span, word
                                        ).rect
                                    ),
                                )
                                # Clear the word list, as we are going for the next word
                                word = []
                            whitespace = SubElement(
                                text_line,
                                "SP",
                                **self.get_element_coordinates(char["bbox"]),
                            )
                        elif len(chars) == 1:
                            # This line have just one charachter, we just write it down
                            text_word = SubElement(
                                text_line,
                                "String",
                                CONTENT=char["c"],
                                **self.get_element_coordinates(
                                    fitz.recover_span_quad(
                                        line["dir"], span, [char]
                                    ).rect
                                ),
                            )
                            # Reset the word
                            word = []
                        elif index == len(chars) - 1:
                            # We hit the end of the line
                            if word:
                                word.append(char)
                                # let's write the word down, without a whitespace
                                text_word = SubElement(
                                    text_line,
                                    "String",
                                    CONTENT="".join([char["c"] for char in word]),
                                    **self.get_element_coordinates(
                                        fitz.recover_span_quad(
                                            line["dir"], span, word
                                        ).rect
                                    ),
                                )
                                # Reset the word
                                word = []
                            else:
                                # We don't have a word. This means the end of the line is a single character
                                # preceeded by a whitespace
                                text_word = SubElement(
                                    text_line,
                                    "String",
                                    CONTENT=char["c"],
                                    **self.self.get_element_coordinates(
                                        fitz.recover_span_quad(
                                            line["dir"], span, [char]
                                        ).rect
                                    ),
                                )
                        else:
                            # We hit another char, let's build a word
                            word.append(char)

        alto_xml = parseString(tostring(alto, encoding="utf-8").decode()).toprettyxml()
        return alto_xml
