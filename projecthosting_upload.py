#!/usr/bin/env python

import sys
import re
import os.path

import allura_issues

# API docs:
#   http://code.google.com/p/support/wiki/IssueTrackerAPIPython
import gdata.projecthosting.client
import gdata.projecthosting.data
import gdata.gauth
import gdata.client
import gdata.data
import atom.http_core
import atom.core

def string_is_nonnegative_number(case):
    try:
      return int(case) >= 0
    except:
      return False

class PatchBot():
    client = gdata.projecthosting.client.ProjectHostingClient()

    # you can use mewes for complete junk testing
    #PROJECT_NAME = "mewes"
    PROJECT_NAME = "lilypond"

    username = None
    password = None

    def get_credentials(self):
        # TODO: can we use the coderview cookie for this?
        #filename = os.path.expanduser("~/.codereview_upload_cookies")
        filename = os.path.expanduser("~/.lilypond-project-hosting-login")
        try:
            login_data = open(filename).readlines()
            self.username = login_data[0]
            self.password = login_data[1]
        except:
            print "Could not find stored credentials"
            print "  %(filename)s" % locals()
            print "Please enter login details manually"
            print
            import getpass
            print "Username (google account name):"
            self.username = raw_input().strip()
            self.password = getpass.getpass()

    def login(self):
        try:
            self.client.client_login(
                self.username, self.password,
                source='lilypond-patch-handler', service='code')
        except:
            print "Incorrect username or password"
            sys.exit(1)


    def create_issue(self, subject, description):
        """Create an issue."""
        issue = self.client.add_issue(
            self.PROJECT_NAME,
            "Patch: " + subject,
            description,
            self.username,
            owner = self.username,
            status = "Started",
            labels = ["Type-Enhancement", "Patch-new"])
        # get the issue number extracted from the URL
        issue_id = int(re.search("[0-9]+", issue.id.text).group(0))
        # update the issue to set the owner
        return self.update_issue(issue_id, "")

    def generate_devel_error(self, issue_id) :
        print "WARNING: could not change issue labels;"
        if issue_id is None:
            print "please email lilypond-devel with a general",
            print "description of the problem"
        else:
            print "please email lilypond-devel with the issue",
            print "number: %s" % issue_id

    def update_issue(self, issue_id, description):
        try:
            issue = self.client.update_issue(
                self.PROJECT_NAME,
                issue_id,
                self.username,
                comment = description,
                owner = self.username,
                status = "Started",
                labels = ["Patch-new"])
        # TODO: this is a bit hack-ish, but I'm new to exceptions
        except gdata.client.RequestError as err:
            if err.body == "No permission to edit issue":
                if description != "":
                    issue = self.client.update_issue(
                        self.PROJECT_NAME,
                        issue_id,
                        self.username,
                        comment = description)
                    self.generate_devel_error(issue_id)
                    print err.body
            elif err.body == "There were no updates performed.":
                pass
            else:
                self.generate_devel_error(issue_id)
                print err.body
                return None
        return issue_id

    def find_fix_issue_id(self, text):
        splittext = re.findall(r'\w+', text)
        issue_id = None
        # greedy search for the issue id
        for i, word in enumerate(splittext):
            if word in ["fix", "issue", "Fix", "Issue"]:
                try:
                    maybe_number = splittext[i+1]
                    if maybe_number[-1] == ")":
                        maybe_number = maybe_number[:-1]
                    issue_id = int(maybe_number)
                    break
                except:
                    pass
        if not issue_id:
            try:
                maybe_number = re.findall(r'\([0-9]+\)', text)
                issue_id = int(maybe_number[0][1:-1])
            except:
                pass
        return issue_id

    def query_user(self, issue = None) :
        query_string1 = "We were not able to associate this patch with a tracker issue." if issue == None else str(issue)+" will not be used as a tracker number."
        print query_string1
        info = raw_input("Please enter a valid tracker issue number\n"
                         "(or enter nothing to create a new issue): ")
        while info and (not string_is_nonnegative_number(info)):
            info = raw_input("This is an invalid entry.  Please enter either an issue number (just digits, no spaces) or nothing to create an issue: ")
        if info:
            return int(info)
        return None

    def upload(self, issue, patchset, subject="", description="", issue_id=None):
        # NB.  issue is the Rietveld issue; issue_id is the Allura issue
        if not subject:
            subject = "new patch"

        # update or create?
        if not issue_id:
            # Looks for issue number in the description
            issue_id = self.find_fix_issue_id(subject+' '+description)
        if issue_id:
            print "This has been identified with issue "+str(issue_id)+"."
            correct = raw_input("Is this correct? [y/n (y)]")
            if correct == 'n':
                issue_id = None
        if not issue_id:
            issue_id = self.query_user(issue_id)

        code_review_url = "https://codereview.appspot.com/" + issue

        if issue_id:
            issue_id = allura_issues.update_issue(issue_id, description,
                                                  code_review_url)
        else:
            # If the subject is repeated as the first paragraph of the
            # description, eliminate the redundancy.
            if description.strip() == subject.strip():
                description = ""
            elif description.startswith(subject + "\n\n"):
                description = description[len(subject):].lstrip("\n")

            # An issue number in the subject line is redundant in the
            # issue tracker (unlike in the code review). Recognize
            # [Xx]+ as a placeholder for a number that was unknown
            # when the user entered the subject.
            subject = re.sub(r"^\s*Issue\s+#?(\d+|[Xx]+):?\s*", "", subject)
            issue_id = allura_issues.create_issue(subject, description,
                                                  code_review_url)
        return issue_id


# hacky integration
def upload(issue, patchset, subject="", description="", issue_id=None):
    patchy = PatchBot()
    status = patchy.upload(issue, patchset, subject, description, issue_id)
    if status:
        print "Tracker issue done: %s" % status
    else:
        print "Problem with the tracker issue"
    return status

