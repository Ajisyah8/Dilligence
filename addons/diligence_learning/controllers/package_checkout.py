from odoo import http
from odoo.http import request


class DiligencePackageCheckoutController(http.Controller):

    @http.route(
        '/diligence/course/<int:course_id>/packages',
        type='http',
        auth='public',
        website=True,
        sitemap=False,
    )
    def course_packages(self, course_id, **kwargs):
        course = request.env['slide.channel'].sudo().browse(course_id).exists()
        if not course or not course._diligence_has_package_product():
            return request.redirect('/shop')

        packages = request.env['product.template'].sudo().search([
            ('diligence_course_ids', 'in', course.id),
            '|',
            ('diligence_package_type_id', '!=', False),
            ('diligence_package_type', '!=', False),
            ('sale_ok', '=', True),
            ('is_published', '=', True),
            ('diligence_sales_status', '=', 'available'),
        ]).filtered(lambda package: (
            package.diligence_has_available_course
            and package.product_variant_id._is_add_to_cart_allowed()
        ))
        tier_order = {'starter': 0, 'community': 1, 'consultation': 2}
        packages = packages.sorted(key=lambda package: (
            tier_order.get(package._diligence_package_type_code(), 3),
            package.diligence_package_type_id.sequence if package.diligence_package_type_id else 100,
            package.name or '',
            package.id,
        ))
        return request.render('diligence_learning.diligence_course_package_selection', {
            'course': course,
            'packages': packages,
        })

    @http.route(
        '/diligence/course/buy',
        type='http',
        auth='public',
        website=True,
        methods=['POST'],
        sitemap=False,
    )
    def buy_course(self, course_id=None, **post):
        """Route course purchase to matching packages or its standalone product."""
        try:
            course_id = int(course_id)
        except (TypeError, ValueError):
            return request.redirect('/shop')

        course = request.env['slide.channel'].sudo().browse(course_id).exists()
        if not course or course.diligence_availability == 'coming_soon':
            return request.redirect('/shop')
        if course._diligence_has_package_product():
            return request.redirect(f'/diligence/course/{course.id}/packages')

        product = course._diligence_standalone_product()
        if not product or not product._is_add_to_cart_allowed():
            return request.redirect('/shop')

        order = request.cart or request.website._create_cart()
        order.sudo()._cart_add(product.id, 1)
        return request.redirect('/shop/cart')

    @http.route(
        '/diligence/package/buy',
        type='http',
        auth='public',
        website=True,
        methods=['POST'],
        sitemap=False,
    )
    def buy_package(self, product_id=None, **post):
        """Add an available learning package to the cart and open checkout."""
        try:
            product_id = int(product_id)
        except (TypeError, ValueError):
            return request.redirect('/shop')

        product = request.env['product.product'].sudo().browse(product_id).exists()
        package = product.product_tmpl_id
        if (
            not product
            or not product.active
            or not product.sale_ok
            or not product.website_published
            or not package._diligence_is_package()
            or package.diligence_sales_status != 'available'
            or not package.diligence_has_available_course
            or not product._is_add_to_cart_allowed()
        ):
            return request.redirect('/shop')

        order = request.cart or request.website._create_cart()
        order.sudo()._cart_add(product.id, 1)
        return request.redirect('/shop/cart')
