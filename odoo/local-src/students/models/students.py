from odoo import fields, models

class StudentsTraining(models.Model):
    _name = "students.training"
    _description = "Training table"
    _rec_name = "code"

    code = fields.Char(string="Training code", size=4, required=True)
    name = fields.Char(string="Training name", size=100, required=True)
    student_ids = fields.One2many(
        string="Training students",
        comodel_name="students.student",
        inverse_name="training_id",
    )

class StudentsStudent(models.Model):
    _name = "students.student"
    _description = "Student table"
    _rec_name = "number"

    number = fields.Char("Student number", size=11, required=True)
    firstname = fields.Char("Student firstname", size=64, required=True)
    lastname = fields.Char("Student lastname", size=64, required=True)
    training_id = fields.Many2one(
        string="Training",
        comodel_name="students.training",
        ondelete="cascade",
    )
    mark_ids = fields.One2many(
        string="marks Students",
        comodel_name="students.mark",
        inverse_name="student_id",
    )


class StudentsMark(models.Model):
    _name = "students.mark"
    _description = "Mark table"

    subject = fields.Char("Subject", size=64, required=True)
    mark = fields.Float("Mark", size=5, required=True)
    student_id = fields.Many2one(
        string="Students",
        comodel_name="students.student",
        ondelete="cascade",
        required=True,
    )