SELECT
  pp.productid,
  pp.name AS product_name,
  COUNT(ssd.productid) AS purchase_count
FROM sales.salesorderdetail AS ssd
JOIN production.product AS pp
  ON ssd.productid = pp.productid
JOIN sales.salesorderheader AS ssh
  ON ssd.salesorderid = ssh.salesorderid
WHERE
  ssh.status <> 6 -- 6 = Cancelled
GROUP BY
  pp.productid,
  pp.name
ORDER BY
  purchase_count DESC
LIMIT 2;

SELECT
  pp.productid,
  pp.name AS product_name,
  COUNT(ssd.productid) AS purchase_count
FROM sales.salesorderdetail AS ssd
JOIN production.product AS pp
  ON ssd.productid = pp.productid
JOIN sales.salesorderheader AS ssh
  ON ssd.salesorderid = ssh.salesorderid
WHERE
  ssh.status <> 6
GROUP BY
  pp.productid,
  pp.name
ORDER BY
  purchase_count DESC
LIMIT 2;

 SELECT
  sp.businessentityid,
  sp.salesquota,
  sp.bonus,
  sp.commissionpct,
  sp.salesytd,
  sp.saleslastyear,
  COUNT(soh.salesorderid) AS total_orders
FROM sales.salesperson AS sp
JOIN sales.salesorderheader AS soh
  ON sp.businessentityid = soh.salespersonid
GROUP BY
  sp.businessentityid,
  sp.salesquota,
  sp.bonus,
  sp.commissionpct,
  sp.salesytd,
  sp.saleslastyear
ORDER BY
  total_orders DESC
LIMIT 5;

SELECT
  sp.businessentityid,
  sp.salesquota,
  sp.bonus,
  sp.commissionpct,
  sp.salesytd,
  sp.saleslastyear,
  COUNT(soh.salesorderid) AS total_orders
FROM sales.salesperson AS sp
LEFT JOIN sales.salesorderheader AS soh
  ON sp.businessentityid = soh.salespersonid
GROUP BY
  sp.businessentityid,
  sp.salesquota,
  sp.bonus,
  sp.commissionpct,
  sp.salesytd,
  sp.saleslastyear
ORDER BY
  total_orders ASC
LIMIT 5;

select count(1) from sales.salesperson;